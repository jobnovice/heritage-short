"""Stage 0: call each provider once, log latency to runs.jsonl, and list the Gemini models this key can use.

    python -m pipeline.smoke
"""
from __future__ import annotations

import base64
import requests

from .common import env, log_run, timed
from . import providers as P


def check(name, fn):
    with timed() as t:
        try:
            note = fn()
            status = "ok"
        except Exception as e:  # smoke test: record every failure, never crash
            note, status = str(e)[:300], "error"
    log_run(stage="smoke", provider=name, status=status, latency_sec=t["sec"], notes=note)
    print(f"  {name:<22} {status:<6} {t['sec']:>6.2f}s  {note[:110] if note else ''}")


def gemini_models():
    key = env("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing")
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 200}, timeout=30)
    r.raise_for_status()
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])]
    interesting = [n for n in names if any(k in n for k in ("flash", "tts", "image", "omni", "veo", "lyria"))]
    return "models: " + ", ".join(interesting)


def gemini_text():
    out = P.gemini_text("Reply with the single Amharic word for 'sea'.", max_tokens=20)
    return f"{P.gemini_text_model()} -> {out.strip()[:40]}"


def gemini_tts():
    pcm = P.gemini_tts("ሰላም", voice="Kore", style="Say warmly:")
    return f"{P.gemini_tts_model()} -> {len(pcm)} bytes PCM ({len(pcm) / 48000:.2f}s)"


def cloudflare():
    acct, tok = env("CLOUDFLARE_ACCOUNT_ID"), env("CLOUDFLARE_API_TOKEN")
    if not (acct and tok):
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN missing (keyframes will use pollinations)")
    img = P.cloudflare_image("a small boat on a calm sea, gouache", seed=1, steps=4)
    return f"{len(img)} bytes image"


def pollinations():
    img = P.pollinations_image("a small boat on a calm sea, gouache", seed=1, size=256)
    return f"{len(img)} bytes image"


def main():
    print("Provider smoke test (each line is also written to runs.jsonl)")
    check("gemini:list_models", gemini_models)
    check("gemini:text", gemini_text)
    check("gemini:tts", gemini_tts)
    check("cloudflare:flux", cloudflare)
    check("pollinations:flux", pollinations)


if __name__ == "__main__":
    main()
