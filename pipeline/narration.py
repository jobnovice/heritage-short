"""Stage: narration. One WAV per shot, so a re-take of one line costs one TTS call.

    python -m pipeline.narration [--only s05] [--force]

Cache key = (provider, model, voice, style instruction, Amharic line). Changing any of these for a
shot regenerates only that shot. Output: outputs/narration/<id>.wav (24 kHz mono) + .meta.json
holding the measured duration that the edit uses to time the picture.
"""
from __future__ import annotations

import argparse
import wave
from pathlib import Path

from . import providers as P
from .common import (OUT, QuotaExhausted, StageReport, ensure_dir, input_hash, is_fresh, load_storyboard,
                     log_run, timed, with_retries, write_meta)

SR = 24000


def write_wav(path: Path, pcm: bytes, sr: int = SR) -> float:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return round(len(pcm) / 2 / sr, 3)


def synth(sb: dict, text: str, shot_id: str) -> tuple[bytes, dict]:
    v = sb["voice"]
    if v["provider"] == "gemini":
        model = v.get("model") or P.gemini_tts_model()
        with timed() as t:
            try:
                pcm = with_retries(lambda: P.gemini_tts(text, voice=v["voice_name"], style=v["style_instruction"], model=model),
                                   what=f"tts {shot_id}")
                status = "ok"
            except Exception as e:
                status, pcm = f"error: {e}"[:300], None
        log_run(stage="narration", shot=shot_id, provider="gemini", model=model,
                params={"voice": v["voice_name"], "style": v["style_instruction"][:80]}, seed=None,
                latency_sec=t["sec"], status=status, chars=len(text), cost_usd=0.0,
                notes="Gemini API free tier")
        if pcm is None:
            raise QuotaExhausted(status)
        return pcm, {"model": model, "latency_sec": t["sec"]}
    if v["provider"] == "addis":
        raise NotImplementedError("Addis AI provider: add the endpoint from their docs in providers.py (see EXPERIMENTS.md)")
    raise ValueError(v["provider"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="shot ids to consider")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    d = ensure_dir(OUT / "narration")
    rep = StageReport("narration")
    v = sb["voice"]
    for s in sb["shots"]:
        if a.only and s["id"] not in a.only:
            continue
        out = d / f"{s['id']}.wav"
        h = input_hash(v["provider"], v.get("model") or P.gemini_tts_model(), v["voice_name"], v["style_instruction"], s["narration"]["am"])
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
    rep.done()


if __name__ == "__main__":
    main()
