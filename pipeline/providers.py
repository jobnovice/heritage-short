"""Thin, logged wrappers around every external model. Each wrapper raises RetryableError for
transient failures and QuotaExhausted when retrying cannot help, so stages can fall back."""
from __future__ import annotations

import base64
import time
import urllib.parse

import requests

from .common import QuotaExhausted, RetryableError, classify_http, env

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models"


def gemini_text_model() -> str:
    return env("GEMINI_TEXT_MODEL", "gemini-2.5-flash")


def gemini_tts_model() -> str:
    return env("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")


def _gemini_key() -> str:
    k = env("GEMINI_API_KEY")
    if not k:
        raise QuotaExhausted("GEMINI_API_KEY is not set")
    return k


def _post(url, **kw):
    try:
        r = requests.post(url, timeout=kw.pop("timeout", 120), **kw)
    except (requests.Timeout, requests.ConnectionError) as e:
        raise RetryableError(f"network: {e}") from e
    classify_http(r)
    return r


def gemini_text(prompt: str, *, model: str | None = None, max_tokens: int = 2048, temperature: float = 0.7,
                json_mode: bool = False) -> str:
    model = model or gemini_text_model()
    cfg = {"maxOutputTokens": max_tokens, "temperature": temperature}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    r = _post(f"{GEMINI}/{model}:generateContent", params={"key": _gemini_key()},
              json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg})
    parts = r.json()["candidates"][0]["content"].get("parts", [])
    return "".join(p.get("text", "") for p in parts)


def gemini_tts(text: str, *, voice: str, style: str, model: str | None = None) -> bytes:
    """Returns raw PCM: 24 kHz, 16-bit, mono."""
    model = model or gemini_tts_model()
    body = {
        "contents": [{"parts": [{"text": f"{style}\n{text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    r = _post(f"{GEMINI}/{model}:generateContent", params={"key": _gemini_key()}, json=body, timeout=180)
    try:
        data = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except (KeyError, IndexError) as e:
        raise RetryableError(f"TTS returned no audio: {r.text[:200]}") from e
    return base64.b64decode(data)


def cloudflare_image(prompt: str, *, seed: int, steps: int = 4,
                     model: str = "@cf/black-forest-labs/flux-1-schnell") -> bytes:
    acct, tok = env("CLOUDFLARE_ACCOUNT_ID"), env("CLOUDFLARE_API_TOKEN")
    if not (acct and tok):
        raise QuotaExhausted("Cloudflare credentials not set")
    r = _post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
              headers={"Authorization": f"Bearer {tok}"},
              json={"prompt": prompt, "seed": seed, "steps": steps})
    j = r.json()
    if not j.get("success", True):
        msg = str(j.get("errors"))
        if "neuron" in msg.lower() or "quota" in msg.lower() or "limit" in msg.lower():
            raise QuotaExhausted(msg)
        raise RetryableError(msg)
    return base64.b64decode(j["result"]["image"])


def pollinations_image(prompt: str, *, seed: int, size: int = 1024, model: str = "flux") -> bytes:
    """Free, keyless FLUX endpoint. Prompts are sent to a third party: keep private details out."""
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
    try:
        r = requests.get(url, params={"width": size, "height": size, "seed": seed, "model": model,
                                      "nologo": "true", "private": "true"}, timeout=180)
    except (requests.Timeout, requests.ConnectionError) as e:
        raise RetryableError(f"network: {e}") from e
    classify_http(r)
    if not r.headers.get("content-type", "").startswith("image"):
        raise RetryableError(f"pollinations returned {r.headers.get('content-type')}")
    return r.content
