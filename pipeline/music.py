"""Stage: music. Writes outputs/music/score.wav and outputs/music/sea.wav (ambience stem).

Providers (storyboard.music.provider):
  qenet   - an original score composed in code from the storyboard's cue list, using Ethiopian
            qenet (pentatonic modes). Deterministic: same cues + seed -> same audio. No GPU.
  acestep - candidates generated with ACE-Step 1.5 on Kaggle (notebooks/acestep_kaggle.py),
            downloaded into outputs/music/candidates/; music.chosen_candidate picks one.
  file    - any other licensed file at music.chosen_candidate.

    python -m pipeline.music [--candidates 3]   # render 3 qenet candidates with different seeds

The leitmotif: one 12-note theme, stated in tizita major for the Massawa dream and returning in
bati major for the ending, so the score "remembers" the dream when grace arrives.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import wave
from pathlib import Path

import numpy as np

from .common import (OUT, ROOT, code_hash, StageReport, ensure_dir, input_hash, is_fresh, load_storyboard, log_run,
                     shot_timing, timed, write_meta)

SR = 44100
SCALES = {
    "tizita_major": [0, 2, 4, 7, 9],
    "tizita_minor": [0, 2, 3, 7, 8],
    "bati_major": [0, 4, 5, 7, 11],
    "bati_minor": [0, 3, 5, 7, 10],
    "ambassel": [0, 1, 5, 7, 8],
    "anchihoye": [0, 1, 5, 6, 9],
}
THEME = [(2, 1), (1, 1), (0, 2), (1, 1), (2, 1), (3, 1), (2, 2), (1, 1), (0, 1), (-1, 1), (0, 3)]  # (degree, beats)


def degree_hz(root: float, scale: list[int], degree: int, octave: int = 0) -> float:
    o, i = divmod(degree, len(scale))
    return root * 2 ** ((scale[i] + 12 * (o + octave)) / 12)


def pluck(f: float, dur: float, amp: float, rng) -> np.ndarray:
    """Krar-like pluck: additive harmonics, faster decay for higher partials, slight inharmonicity."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for k in range(1, 8):
        fk = f * k * (1 + 0.0008 * k * k)
        sig += (1 / k ** 1.4) * np.exp(-t * (1.6 + 1.3 * k)) * np.sin(2 * np.pi * fk * t + rng.uniform(0, 6.28))
    env = np.minimum(1, t / 0.004)
    return amp * sig * env


def drone(f: float, n: int, amp: float) -> np.ndarray:
    t = np.arange(n) / SR
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.07 * t)
    s = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.5 * t) + 0.25 * np.sin(2 * np.pi * f * 2.002 * t)
    return amp * lfo * s / 1.75


def sea(n: int, seed: int) -> np.ndarray:
    """Waves: brown noise, low-passed, with slow swells."""
    rng = np.random.default_rng(seed + 1000)
    w = np.cumsum(rng.normal(0, 1, n))
    w -= np.convolve(w, np.ones(4410) / 4410, mode="same")  # remove drift
    k = np.ones(40) / 40
    w = np.convolve(w, k, mode="same")
    t = np.arange(n) / SR
    swell = 0.55 + 0.45 * np.sin(2 * np.pi * t / 7.3) * np.sin(2 * np.pi * t / 11.1 + 1)
    w = w / (np.abs(w).max() + 1e-9)
    return 0.5 * w * swell


def compose(sb: dict, timing: list[dict], seed: int) -> tuple[np.ndarray, np.ndarray]:
    m = sb["music"]
    rng = np.random.default_rng(seed)
    root, beat = m.get("root_hz", 146.83), 60 / m.get("tempo_bpm", 60)
    total = timing[-1]["start"] + timing[-1]["duration"] + sb.get("end_card", {}).get("duration_sec", 3.5)
    n = int(total * SR) + SR
    out = np.zeros(n)
    starts = {t["id"]: t["start"] for t in timing}
    cues = sorted(m["cues"], key=lambda c: starts[c["starts_at_shot"]])
    for i, cue in enumerate(cues):
        a = starts[cue["starts_at_shot"]]
        b = starts[cues[i + 1]["starts_at_shot"]] if i + 1 < len(cues) else total
        if cue["mode"] == "silence":
            continue
        seg = np.zeros(int((b - a + 4) * SR))
        scale, inten = SCALES[cue["mode"]], cue["intensity"]
        seg[: int((b - a + 2) * SR)] += drone(root / 2, int((b - a + 2) * SR), 0.10 + 0.12 * inten)
        t = 0.6 * rng.random()
        theme_cue = cue["mode"] in ("tizita_major", "bati_major")
        step = 0
        while t < (b - a) - 0.5:
            if theme_cue:
                deg, beats = THEME[step % len(THEME)]
                step += 1
            else:  # sparse wandering notes: fewer at low intensity
                deg, beats = int(rng.integers(-2, 4)), float(rng.choice([1, 2, 2, 3]))
                if rng.random() > 0.35 + inten:
                    t += beats * beat
                    continue
            f = degree_hz(root, scale, deg, octave=1)
            note = pluck(f, 2.8, 0.22 + 0.35 * inten, rng)
            if rng.random() < 0.25:  # krar ornament: grace note a degree above
                note[: len(note) // 2] += 0.4 * pluck(degree_hz(root, scale, deg + 1, 1), 1.4, 0.15, rng)
            j = int(t * SR)
            seg[j: j + len(note)] += note[: len(seg) - j]
            t += beats * beat * (1.0 if theme_cue else 1 + 0.1 * rng.random())
        fade = int(1.5 * SR)
        seg[:fade] *= np.linspace(0, 1, fade)
        end = int((b - a + 2) * SR)
        seg[end - fade:end] *= np.linspace(1, 0, fade)
        seg[end:] = 0
        j = int(a * SR)
        out[j: j + len(seg)] += seg[: n - j]
    # final fade over the end card
    tail = int(3 * SR)
    out[-tail:] *= np.linspace(1, 0, tail)
    out /= max(1.0, np.abs(out).max() / 0.8)
    return out, sea(n, seed)


def write(path: Path, x: np.ndarray) -> None:
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=int, default=0, help="render N qenet candidates (seeds seed..seed+N-1)")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    m = sb["music"]
    d = ensure_dir(OUT / "music")
    timing = shot_timing(sb)
    rep = StageReport("music")
    if a.candidates:
        cd = ensure_dir(d / "candidates")
        for k in range(a.candidates):
            s = m.get("seed", 7) + k
            with timed() as t:
                score, _ = compose(sb, timing, s)
                write(cd / f"qenet_seed{s}.wav", score)
            log_run(stage="music", provider="qenet", model="qenet-composer-v1", seed=s, latency_sec=t["sec"],
                    status="ok", cost_usd=0.0, notes="candidate")
            print(f"  candidate {cd / f'qenet_seed{s}.wav'}")
        return
    score_out, sea_out = d / "score.wav", d / "sea.wav"
    if m["provider"] == "qenet":
        h = input_hash("qenet-v1", code_hash(sys.modules[__name__]), m, timing)
        if is_fresh(score_out, h):
            rep.hit("score")
        else:
            with timed() as t:
                score, waves = compose(sb, timing, m.get("seed", 7))
                write(score_out, score)
                write(sea_out, waves)
            log_run(stage="music", provider="qenet", model="qenet-composer-v1", seed=m.get("seed", 7),
                    params={"tempo": m.get("tempo_bpm"), "root_hz": m.get("root_hz"),
                            "cues": [(c["id"], c["mode"], c["intensity"]) for c in m["cues"]]},
                    latency_sec=t["sec"], status="ok", cost_usd=0.0, gpu_min=0)
            write_meta(score_out, h, provider="qenet")
            rep.miss("score")
    else:
        src = ROOT / m["chosen_candidate"]
        h = input_hash(m["provider"], str(src), src.stat().st_mtime)
        if is_fresh(score_out, h):
            rep.hit("score")
        else:
            shutil.copy(src, score_out)
            if not sea_out.exists():
                write(sea_out, sea(int((timing[-1]["start"] + timing[-1]["duration"] + 6) * SR), 7))
            write_meta(score_out, h, provider=m["provider"], source=str(src))
            rep.miss("score", f"from {src.name}")
    rep.done()


if __name__ == "__main__":
    main()
