"""Stage: narration. One WAV per shot.

    python -m pipeline.narration [--only s05] [--force]

voice.take = "per_line": one TTS call per shot; cache key = (provider, model, voice, style, line), so a
re-take of one line costs one call. Separate takes drift in pitch and pace, though (E16: 112-174 Hz).
voice.take = "single": the whole script in ONE call (one performance, one voice), split back into
lines at pauses by dynamic programming; the key covers every line, so any edit re-records the take
(still one call). Output: outputs/narration/<id>.wav (24 kHz mono) + .meta.json with the duration
the edit uses to time the picture.
"""
from __future__ import annotations

import argparse
import base64
import difflib
import re
import wave
from pathlib import Path

import numpy as np

from . import providers as P
from .common import (OUT, QuotaExhausted, RetryableError, read_meta, StageReport, ensure_dir, input_hash, is_fresh, load_storyboard,
                     log_run, timed, with_retries, write_meta)

SR = 24000


def write_wav(path: Path, pcm: bytes, sr: int = SR) -> float:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return round(len(pcm) / 2 / sr, 3)


def max_plausible_sec(text: str) -> float:
    """Measured on clean takes: ~0.5-1.0 s per Amharic word. Anything far beyond that means the model
    spoke something extra (it read the style instruction aloud on 8/11 lines - FAILURES.md F7)."""
    return 1.3 * len(text.split()) + 2.0


def synth(sb: dict, text: str, shot_id: str) -> tuple[bytes, dict]:
    v = sb["voice"]
    if v["provider"] == "gemini":
        primary = v.get("model") or P.gemini_tts_model()
        # free-tier quotas are per model per day (F8): on a daily 429, move down the chain at once
        chain = [primary] + [m for m in v.get("fallback_models", []) if m != primary]
        for model in chain:
            def call(model=model):
                pcm = P.gemini_tts(text, voice=v["voice_name"], style=v["style_instruction"], model=model)
                dur = len(pcm) / 2 / SR
                if dur > max_plausible_sec(text):
                    log_run(stage="narration", shot=shot_id, provider="gemini", model=model, status="rejected_too_long",
                            duration_sec=round(dur, 2), max_sec=max_plausible_sec(text), cost_usd=0.0)
                    raise RetryableError(f"take is {dur:.1f}s, max plausible {max_plausible_sec(text):.1f}s")
                return pcm

            with timed() as t:
                try:
                    pcm = with_retries(call, attempts=3, what=f"tts {shot_id} [{model}]")
                    status = "ok"
                except Exception as e:
                    status, pcm = f"error: {e}"[:300], None
            log_run(stage="narration", shot=shot_id, provider="gemini", model=model,
                    params={"voice": v["voice_name"], "style": v["style_instruction"][:80]}, seed=None,
                    latency_sec=t["sec"], status=status, chars=len(text), cost_usd=0.0,
                    notes="Gemini API free tier" + ("" if model == primary else f"; fallback from {primary}"))
            if pcm is not None:
                return pcm, {"model": model, "latency_sec": t["sec"]}
            print(f"    {shot_id}: {model} unavailable -> next model")
        raise QuotaExhausted(status)
    if v["provider"] == "addis":
        with timed() as t:
            try:
                pcm = with_retries(lambda: P.addis_tts(text), what=f"addis {shot_id}")
                status = "ok"
            except Exception as e:
                status, pcm = f"error: {e}"[:300], None
        log_run(stage="narration", shot=shot_id, provider="addis", model="addis-ai-tts-v1", seed=None,
                latency_sec=t["sec"], status=status, chars=len(text), cost_usd=0.0, notes="Addis AI free key")
        if pcm is None:
            raise QuotaExhausted(status)
        return pcm, {"model": "addis-ai-tts-v1", "latency_sec": t["sec"]}
    raise ValueError(v["provider"])


def normalise(t: str) -> str:
    return re.sub(r"[\s\.,!?:;«»\"'።፣፤፥፦]", "", t)


def verify(sb: dict, shot: dict, wav: Path) -> dict:
    """ASR round trip: transcribe the take with Gemini and compare to the script (character similarity).
    A cheap, automatic stand-in for a native-speaker listen; it does not replace one."""
    model = "gemini-3.5-transcribe"
    b64 = base64.b64encode(wav.read_bytes()).decode()
    with timed() as t:
        try:
            r = P._post(f"{P.GEMINI}/{model}:generateContent", params={"key": P._gemini_key()},
                        json={"contents": [{"parts": [{"text": "Transcribe this audio verbatim in its original language and script. Output only the transcript."},
                                                      {"inlineData": {"mimeType": "audio/wav", "data": b64}}]}]})
            heard = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            status = "ok"
        except Exception as e:
            heard, status = "", f"error: {e}"[:200]
    sim = round(difflib.SequenceMatcher(None, normalise(shot["narration"]["am"]), normalise(heard)).ratio(), 3) if heard else None
    if re.search(r"[A-Za-z]{3,}", heard):  # any English words in an Amharic take = spoken instructions
        sim = min(sim or 0, 0.5)
    log_run(stage="narration_verify", shot=shot["id"], provider="gemini", model=model, latency_sec=t["sec"],
            status=status, similarity=sim, heard=heard[:300], cost_usd=0.0)
    return {"asr_text": heard, "asr_similarity": sim}


def narration_key(sb, shot) -> str:
    v = sb["voice"]
    text = shot["narration"]["am"]
    if v.get("take") == "single":  # every shot shares the take, so the key covers every line
        text = [s["narration"]["am"] for s in sb["shots"]]
    return input_hash(v["provider"], v.get("model") or P.gemini_tts_model(), v["voice_name"], v["style_instruction"],
                      text)


def split_take(pcm: bytes, texts: list[str], sr: int = SR) -> list[bytes]:
    """Cut one continuous take into len(texts) lines. Pauses between lines (0.7-1.5 s) are not reliably
    longer than pauses inside them, so 'the N-1 longest gaps' fails (E16). Instead: every silence
    >= 0.25 s is a candidate cut, and dynamic programming picks the N-1 cuts whose segment lengths best
    match each line's expected length (its character share of the take), with a small bonus for long gaps."""
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    hop = sr // 100
    env = np.sqrt(np.add.reduceat(x[: len(x) // hop * hop] ** 2, np.arange(0, len(x) // hop * hop, hop)) / hop)
    db = 20 * np.log10(env + 1e-9)
    sil = db < db.max() - 40
    runs, i = [], 0
    while i < len(sil):
        if sil[i]:
            j = i
            while j < len(sil) and sil[j]:
                j += 1
            if i > 0 and j < len(sil) and j - i >= 25:
                runs.append((i, j))
            i = j
        else:
            i += 1
    n, T = len(texts), len(sil) / 100
    if len(runs) < n - 1:
        raise RetryableError(f"take has {len(runs)} pauses, need {n - 1}")
    pts = [0.0] + [(a + b) / 200 for a, b in runs] + [T]
    gap = [0.0] + [(b - a) / 100 for a, b in runs] + [0.0]
    chars = np.array([len(t.replace(" ", "")) for t in texts], float)
    exp = chars / chars.sum() * T
    C = len(pts) - 1
    best = {(0, 0): (0.0, None)}
    for k in range(1, n + 1):
        for j in ([C] if k == n else range(1, C)):
            opts = [(c + ((pts[j] - pts[p]) / exp[k - 1] - 1) ** 2 - 0.3 * gap[j], p)
                    for (kk, p), (c, _) in best.items() if kk == k - 1 and p < j]
            if opts:
                best[(k, j)] = min(opts)
    cuts, j = [C], C
    for k in range(n, 0, -1):
        j = best[(k, j)][1]
        cuts.append(j)
    cuts = [pts[j] for j in reversed(cuts)]
    out, pad = [], int(0.06 * sr)
    for a, b in zip(cuts, cuts[1:]):
        seg = (x[int(a * sr): int(b * sr)] * 32768).astype("<i2")
        loud = np.where(np.abs(seg) > 0.01 * 32768)[0]
        if len(loud):
            seg = seg[max(0, loud[0] - pad): loud[-1] + pad]
        out.append(seg.tobytes())
    return out


def single_take(sb: dict, d: Path, rep: StageReport, force: bool) -> None:
    shots = sb["shots"]
    h = narration_key(sb, shots[0])
    if not force and all(is_fresh(d / f"{s['id']}.wav", h) for s in shots):
        for s in shots:
            rep.hit(s["id"])
        return
    texts = [s["narration"]["am"] for s in shots]
    try:
        # a blank line between lines invites a clear pause; the guard scales with the whole script
        pcm, info = synth(sb, "\n\n".join(texts), "take")
    except QuotaExhausted as e:
        for s in shots:
            rep.fallback(s["id"], f"TTS unavailable: {e}"[:200])
        return
    take = d / "_take.wav"
    write_wav(take, pcm)
    write_meta(take, h, duration_sec=round(len(pcm) / 2 / SR, 3), **info)
    for s, seg in zip(shots, split_take(pcm, texts)):
        out = d / f"{s['id']}.wav"
        dur = write_wav(out, seg)
        write_meta(out, h, duration_sec=dur, text=s["narration"]["am"], take="single", **info)
        rep.miss(s["id"], f"{dur:.2f}s")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="shot ids to consider")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--verify", action="store_true", help="ASR round-trip check of every take")
    ap.add_argument("--provider", help="override voice.provider (for A/B experiments)")
    ap.add_argument("--outdir", default="narration", help="write under outputs/<outdir> (experiments keep the main take untouched)")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    if a.provider:
        sb["voice"]["provider"] = a.provider
    d = ensure_dir(OUT / a.outdir)
    rep = StageReport("narration")
    v = sb["voice"]
    if v.get("take") == "single":
        single_take(sb, d, rep, a.force)
    for s in ([] if v.get("take") == "single" else sb["shots"]):
        if a.only and s["id"] not in a.only:
            continue
        out = d / f"{s['id']}.wav"
        h = narration_key(sb, s)
        if not a.force and is_fresh(out, h):
            rep.hit(s["id"])
            continue
        try:
            pcm, info = synth(sb, s["narration"]["am"], s["id"])
        except QuotaExhausted as e:
            rep.fallback(s["id"], f"TTS unavailable: {e}"[:200])
            continue
        dur = write_wav(out, pcm)
        write_meta(out, h, duration_sec=dur, text=s["narration"]["am"], **info)
        rep.miss(s["id"], f"{dur:.2f}s")
    models = {read_meta(d / f"{s['id']}.wav").get("model") for s in sb["shots"] if (d / f"{s['id']}.wav").exists()}
    if len(models) > 1:  # F12: a fallback chain can switch models mid-film and change the voice's character
        print(f"  WARNING: narration takes come from {len(models)} models {sorted(map(str, models))}; "
              f"the voice may not match across shots. Pin voice.model or rerun with --force.")
        log_run(stage="narration", kind="consistency_warning", models=sorted(map(str, models)))
    if a.verify:
        import json
        from .common import meta_path
        for s in sb["shots"]:
            out = d / f"{s['id']}.wav"
            if out.exists():
                m = read_meta(out)
                m.update(verify(sb, s, out))
                meta_path(out).write_text(json.dumps(m, ensure_ascii=False, indent=2))
                print(f"  [verify] {s['id']}: similarity {m['asr_similarity']}  heard: {m['asr_text'][:60]}")
    rep.done()


if __name__ == "__main__":
    main()
