"""Blind voice benchmark: the same Amharic lines from three TTS voices, labelled A/B/C in a random
(seeded) order per line, so listeners cannot tell which provider is which.

    python -m pipeline.benchmark render        # writes outputs/benchmark/*.wav + blind_key.json
    python -m pipeline.benchmark score         # reads benchmark/votes.json, writes the results table

The key is kept out of the listening folder; reveal it only after the votes are in.
"""
from __future__ import annotations

import json
import random
import sys
import wave

from . import providers as P
from .common import OUT, ROOT, ffmpeg, ensure_dir, load_storyboard, log_run, timed, with_retries

LINES = ["s03", "s06", "s10"]  # a place name (ምጽዋ), quoted speech, and the emotional turn
VOICES = {
    "gemini_charon": lambda t: P.gemini_tts(t, voice="Charon", style="", model="gemini-3.1-flash-tts-preview"),
    "addis_default": lambda t: P.addis_tts(t),
    "edge_ameha": lambda t: P.edge_tts(t),
}


def write_wav(path, pcm):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)


def render():
    sb = load_storyboard()
    d = ensure_dir(OUT / "benchmark")
    rng = random.Random(2026)
    key = {}
    for sid in LINES:
        text = next(s for s in sb["shots"] if s["id"] == sid)["narration"]["am"]
        order = list(VOICES)
        rng.shuffle(order)
        key[sid] = dict(zip("ABC", order))
        for letter, name in key[sid].items():
            reuse = OUT / "narration" / f"{sid}.wav"
            if name == "gemini_charon" and reuse.exists():  # the film's own take: identical voice/model/text
                pcm = wave.open(str(reuse)).readframes(10 ** 9)
                status, sec = "reused film take", 0.0
            else:
                with timed() as t:
                    pcm = with_retries(lambda: VOICES[name](text), what=f"{name} {sid}")
                status, sec = "ok", t["sec"]
                log_run(stage="benchmark", shot=sid, provider=name.split("_")[0], model=name, latency_sec=sec,
                        status=status, cost_usd=0.0)
            write_wav(d / f"{sid}_{letter}.wav", pcm)
            # equal loudness: listeners prefer louder clips, which would bias the vote
            tmp = d / "_tmp.wav"
            ffmpeg("-i", str(d / f"{sid}_{letter}.wav"), "-af", "loudnorm=I=-20:TP=-2", "-ar", "24000", str(tmp))
            tmp.replace(d / f"{sid}_{letter}.wav")
            print(f"  {sid}_{letter}.wav  ({status})")
    bk = ensure_dir(ROOT / "benchmark")
    (bk / "blind_key.json").write_text(json.dumps(key, indent=2))
    if not (bk / "votes.json").exists():
        (bk / "votes.json").write_text(json.dumps({"_how": "one entry per listener: favourite letter per line, plus a note",
                                                   "listeners": [{"who": "[FILL IN]", "s03": "", "s06": "", "s10": "", "note": ""}]},
                                                  ensure_ascii=False, indent=2))
    print("send the outputs/benchmark/*.wav files (not benchmark/blind_key.json) to >= 5 listeners")


def score():
    bk = ROOT / "benchmark"
    key = json.loads((bk / "blind_key.json").read_text())
    votes = json.loads((bk / "votes.json").read_text())["listeners"]
    tally = {v: 0 for v in VOICES}
    for lis in votes:
        for sid in LINES:
            if lis.get(sid) in ("A", "B", "C"):
                tally[key[sid][lis[sid]]] += 1
    n = sum(tally.values())
    rows = "\n".join(f"| {v} | {c} | {c / n * 100:.0f}% |" for v, c in sorted(tally.items(), key=lambda kv: -kv[1])) if n else ""
    out = f"Listeners: {len(votes)}, votes: {n}\n\n| voice | votes | share |\n|---|---|---|\n{rows}\n"
    (bk / "RESULTS.md").write_text("# Blind voice benchmark results\n\n" + out)
    print(out)


if __name__ == "__main__":
    {"render": render, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "render"]()
