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
    return env("GEMINI_TEXT_MODEL", "gemini-3.8-flash")


def gemini_tts_model() -> str:
    return env("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")


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
    # thinking tokens count against maxOutputTokens: a 20-token budget returned "" (FAILURES.md F6)
    cfg = {"maxOutputTokens": max_tokens, "temperature": temperature, "thinkingConfig": {"thinkingBudget": 0}}
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
        "contents": [{"parts": [{"text": f"{style} {text}" if style else text}]}],  # F7: prefixes get spoken
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


def cloudflare_image(prompt: str, *, seed: int, steps: int = 4, size: int = 1024, refs: list | None = None,
                     model: str = "@cf/black-forest-labs/flux-2-klein-4b") -> bytes:
    """FLUX.2 models take multipart form data and up to 4 reference images (input_image_0..3);
    FLUX.1 schnell takes JSON and rejects a seed (see FAILURES.md F6)."""
    acct, tok = env("CLOUDFLARE_ACCOUNT_ID"), env("CLOUDFLARE_API_TOKEN")
    if not (acct and tok):
        raise QuotaExhausted("Cloudflare credentials not set")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"
    hdr = {"Authorization": f"Bearer {tok}"}
    if "flux-2" in model:
        import io
        from PIL import Image
        files = {"prompt": (None, prompt), "width": (None, str(size)), "height": (None, str(size)),
                 "seed": (None, str(seed))}
        for i, ref in enumerate((refs or [])[:4]):
            b = io.BytesIO()
            im = Image.open(ref).convert("RGB")
            im.thumbnail((768, 768))
            im.save(b, "JPEG", quality=90)
            files[f"input_image_{i}"] = (f"ref{i}.jpg", b.getvalue(), "image/jpeg")
        r = _post(url, headers=hdr, files=files)
    else:
        r = _post(url, headers=hdr, json={"prompt": prompt, "steps": steps})
    j = r.json()
    if not j.get("success", True):
        msg = str(j.get("errors"))
        if "neuron" in msg.lower() or "quota" in msg.lower() or "limit" in msg.lower():
            raise QuotaExhausted(msg)
        raise RetryableError(msg)
    return base64.b64decode(j["result"]["image"])


_POLL_LAST = [0.0]
POLL_GAP = 46.0  # measured free limit: 1 image / 45 s / IP (HTTP 402 FREE_LIMIT), see FAILURES.md F5


def pollinations_image(prompt: str, *, seed: int, size: int = 1024, model: str = "flux") -> bytes:
    """Free, keyless FLUX endpoint. Prompts are sent to a third party: keep private details out.
    Self-throttles to the measured free limit instead of burning retries on 402s."""
    wait = POLL_GAP - (time.time() - _POLL_LAST[0])
    if wait > 0:
        print(f"    pollinations: throttling {wait:.0f}s (free tier 1 img/45s)")
        time.sleep(wait)
    _POLL_LAST[0] = time.time()
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
    try:
        r = requests.get(url, params={"width": size, "height": size, "seed": seed, "model": model,
                                      "nologo": "true", "private": "true"}, timeout=180)
    except (requests.Timeout, requests.ConnectionError) as e:
        raise RetryableError(f"network: {e}") from e
    if r.status_code == 402 and "FREE_LIMIT" in r.text:
        import re
        m = re.search(r"Retry after (\d+)s", r.text)
        time.sleep(int(m.group(1)) + 2 if m else POLL_GAP)
        raise RetryableError("402 FREE_LIMIT")
    classify_http(r)
    if not r.headers.get("content-type", "").startswith("image"):
        raise RetryableError(f"pollinations returned {r.headers.get('content-type')}")
    return r.content


def addis_tts(text: str, *, language: str = "am") -> bytes:
    """Addis AI (Ethiopian Amharic-first model). Endpoint found by probing; no public docs located
    (FAILURES.md F9). Returns raw PCM 24 kHz s16 mono, resampled from the 44.1 kHz WAV it sends."""
    import subprocess
    k = env("ADDIS_AI_API_KEY")
    if not k:
        raise QuotaExhausted("ADDIS_AI_API_KEY is not set")
    r = _post("https://api.addisassistant.com/api/v1/audio", headers={"x-api-key": k},
              json={"text": text, "language": language}, timeout=120)
    try:
        wav = base64.b64decode(r.json()["audio"])
    except (KeyError, ValueError) as e:
        raise RetryableError(f"Addis returned no audio: {r.text[:200]}") from e
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "24000", "pipe:1"],
                       input=wav, capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[:200])
    return p.stdout
