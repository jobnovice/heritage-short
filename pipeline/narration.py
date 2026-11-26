"""Stage: narration. One WAV per shot, so a re-take of one line costs one TTS call.

    python -m pipeline.narration [--only s05] [--force]

Cache key = (provider, model, voice, style instruction, Amharic line). Changing any of these for a
shot regenerates only that shot. Output: outputs/narration/<id>.wav (24 kHz mono) + .meta.json
holding the measured duration that the edit uses to time the picture.
"""
from __future__ import annotations

import argparse
import base64
import difflib
import re
import wave
from pathlib import Path

from . import providers as P
from .common import (OUT, QuotaExhausted, RetryableError, StageReport, ensure_dir, input_hash, is_fresh, load_storyboard,
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
    return input_hash(v["provider"], v.get("model") or P.gemini_tts_model(), v["voice_name"], v["style_instruction"],
                      shot["narration"]["am"])


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
    for s in sb["shots"]:
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
    if a.verify:
        import json
        from .common import meta_path, read_meta
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
