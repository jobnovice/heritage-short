"""Shared plumbing for every stage: env, storyboard validation, input-hash caching,
retries and the runs.jsonl call log.

Rule of the house: a stage never decides *what* to make. It reads storyboard.json,
computes a hash of exactly the inputs that affect its output, and regenerates only
when that hash changed.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"
OUT = ROOT / "outputs"
RUNS = ROOT / "runs.jsonl"
RUN_ID = os.environ.get("HS_RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4]


# ---------------------------------------------------------------- env
def load_env() -> None:
    """Minimal .env loader (no dependency). Real environment variables win."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name, "")
    return v if v else default


# ---------------------------------------------------------------- storyboard
def load_storyboard(path: Path = STORYBOARD) -> dict:
    import jsonschema

    sb = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text())
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(sb), key=lambda e: list(e.path))
    if errors:
        for e in errors:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            print(f"  schema error at {loc}: {e.message}", file=sys.stderr)
        sys.exit(f"storyboard.json failed validation ({len(errors)} errors)")
    _semantic_checks(sb)
    return sb


def _semantic_checks(sb: dict) -> None:
    """Rules JSON Schema cannot express."""
    ids = [s["id"] for s in sb["shots"]]
    problems = []
    if len(ids) != len(set(ids)):
        problems.append("duplicate shot ids")
    for s in sb["shots"]:
        for c in s["characters"]:
            if c not in sb["characters"]:
                problems.append(f"{s['id']}: unknown character '{c}'")
    for cue in sb["music"]["cues"]:
        if cue["starts_at_shot"] not in ids:
            problems.append(f"cue {cue['id']}: unknown shot {cue['starts_at_shot']}")
    for name, c in sb["characters"].items():
        if c.get("real_person") and not c.get("consent_ref"):
            problems.append(f"character '{name}' is a real person but has no consent_ref (see ETHICS.md)")
    if problems:
        for p in problems:
            print("  semantic error:", p, file=sys.stderr)
        sys.exit("storyboard.json failed semantic checks")


# ---------------------------------------------------------------- hashing / cache
def input_hash(*parts) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def code_hash(*modules) -> str:
    """Code is an input too: hashing a stage's source means a renderer fix invalidates its outputs."""
    return input_hash(*[file_hash(Path(m.__file__)) for m in modules])


def meta_path(out: Path) -> Path:
    return out.with_suffix(out.suffix + ".meta.json")


def is_fresh(out: Path, h: str) -> bool:
    m = meta_path(out)
    if not (out.exists() and m.exists()):
        return False
    try:
        return json.loads(m.read_text()).get("input_hash") == h
    except json.JSONDecodeError:
        return False


def write_meta(out: Path, h: str, **extra) -> None:
    meta_path(out).write_text(json.dumps({"input_hash": h, "run_id": RUN_ID, "written_at": now(), **extra},
                                         ensure_ascii=False, indent=2))


def read_meta(out: Path) -> dict:
    m = meta_path(out)
    return json.loads(m.read_text()) if m.exists() else {}


# ---------------------------------------------------------------- logging
def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_run(**fields) -> None:
    """Append one JSON line to runs.jsonl. Called for every model call (and once per stage summary)."""
    rec = {"ts": now(), "run_id": RUN_ID, **fields}
    with open(RUNS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class StageReport:
    """Collects which shots were regenerated vs served from cache, and logs a summary line."""

    def __init__(self, stage: str):
        self.stage, self.regenerated, self.cached, self.fallbacks, self.t0 = stage, [], [], [], time.time()

    def hit(self, key):
        self.cached.append(key)
        print(f"  [{self.stage}] {key}: cached")

    def miss(self, key, note=""):
        self.regenerated.append(key)
        print(f"  [{self.stage}] {key}: REGENERATED {note}")

    def fallback(self, key, why):
        self.fallbacks.append({"key": key, "why": why})
        print(f"  [{self.stage}] {key}: fallback ({why})")

    def done(self):
        log_run(stage=self.stage, kind="stage_summary", regenerated=self.regenerated, cached=self.cached,
                fallbacks=self.fallbacks, wall_sec=round(time.time() - self.t0, 2))
        print(f"[{self.stage}] regenerated={self.regenerated or '-'} cached={len(self.cached)} "
              f"fallbacks={len(self.fallbacks)} ({time.time() - self.t0:.1f}s)")


# ---------------------------------------------------------------- retries
class RetryableError(Exception):
    """Raise for 429 / 5xx / timeouts: worth another try."""


class QuotaExhausted(Exception):
    """Raise when retrying cannot help today (daily quota gone): caller should fall back."""


def with_retries(fn, *, attempts: int = 3, base: float = 2.0, what: str = "call"):
    """Exponential backoff with jitter. Three attempts, then the caller's fallback takes over."""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except RetryableError as e:
            last = e
            wait = base * (2 ** i) + random.uniform(0, 1)
            print(f"    {what}: attempt {i + 1}/{attempts} failed ({e}); retrying in {wait:.1f}s")
            time.sleep(wait)
    raise QuotaExhausted(f"{what} failed after {attempts} attempts: {last}")


@contextmanager
def timed():
    t = {"start": time.time()}
    yield t
    t["sec"] = round(time.time() - t["start"], 3)


def classify_http(resp) -> None:
    """Turn an HTTP response into the right exception type."""
    if resp.status_code < 400:
        return
    body = resp.text[:300]
    if resp.status_code == 429:
        if "quota" in body.lower() and ("day" in body.lower() or "daily" in body.lower()):
            raise QuotaExhausted(f"429 daily quota: {body}")
        raise RetryableError(f"429 rate limited: {body}")
    if resp.status_code >= 500:
        raise RetryableError(f"{resp.status_code}: {body}")
    raise RuntimeError(f"HTTP {resp.status_code}: {body}")


# ---------------------------------------------------------------- media helpers
def ffmpeg(*args: str, quiet: bool = True) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner"] + (["-loglevel", "error"] if quiet else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + " ".join(cmd) + "\n" + r.stderr[-2000:])


def probe_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def shot_timing(sb: dict) -> list[dict]:
    """Picture is cut to the voice: each shot lasts max(storyboard minimum, narration + lead-in + tail).
    Narration durations come from the narration stage's meta files, so run narration first."""
    v = sb["voice"]
    lead, tail = v.get("lead_in_sec", 0.4), v.get("tail_sec", 0.6)
    t, out = 0.0, []
    for s in sb["shots"]:
        wav = OUT / "narration" / f"{s['id']}.wav"
        nd = read_meta(wav).get("duration_sec", 0.0) if wav.exists() else 0.0
        dur = round(max(s["duration_sec"], (nd + lead + tail) if nd else 0), 2)
        out.append({"id": s["id"], "start": round(t, 2), "duration": dur, "narration_sec": nd, "voice_at": round(t + lead, 2)})
        t += dur
    return out


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p
