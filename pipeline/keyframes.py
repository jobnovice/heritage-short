"""Stage: keyframes. Character reference sheets first, then one keyframe per shot conditioned on them.

    python -m pipeline.keyframes [--only s05] [--sheets-only] [--candidates 4]

Consistency strategy (no LoRA, no image-reference input on the free FLUX endpoints):
  - one fixed character description pasted verbatim into every prompt ({uncle_young} placeholders),
  - one fixed style block appended to every prompt,
  - a fixed seed per character (shot seed = character seed + shot number unless the shot sets one),
  - the reference sheet is generated with the same text and checked by eye against each keyframe.

Provider chain: storyboard.style.keyframe_provider first, then the others, then a placeholder card
(so the edit never blocks). Every call is logged; fallbacks are recorded in the stage summary.
"""
from __future__ import annotations

import argparse
import re

from PIL import Image, ImageDraw

from . import providers as P
from .cards import font
from .common import (OUT, file_hash, QuotaExhausted, StageReport, ensure_dir, input_hash, is_fresh, load_storyboard,
                     log_run, timed, with_retries, write_meta)

CHAIN = ["cloudflare", "pollinations", "placeholder"]
LIST_PRICE = {"cloudflare": 0.0011, "pollinations": 0.0, "placeholder": 0.0}  # USD/image list-price equivalent


def expand(sb: dict, text: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: sb["characters"][m.group(1)]["description"], text)


def full_prompt(sb: dict, body: str) -> str:
    return f"{expand(sb, body)}. {sb['style']['block']}. Avoid: {sb['style']['negative']}"


def shot_seed(sb: dict, shot: dict) -> int:
    if "seed" in shot:
        return shot["seed"]
    base = sb["characters"][shot["characters"][0]]["seed"] if shot["characters"] else 9000
    return base + int(shot["id"][1:])


def placeholder(prompt: str, size: int) -> bytes:
    import io
    img = Image.new("RGB", (size, size), (28, 44, 52))
    d = ImageDraw.Draw(img)
    f = font(28)
    import textwrap
    for i, line in enumerate(textwrap.wrap(prompt[:400], 52)):
        d.text((40, 40 + i * 38), line, font=f, fill=(230, 220, 200))
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def generate(sb: dict, prompt: str, seed: int, key: str, refs: list | None = None) -> tuple[bytes, str, str]:
    st = sb["style"]
    first = st.get("keyframe_provider", "cloudflare")
    chain = [first] + [p for p in CHAIN if p != first]
    size = st.get("keyframe_size", 1024)
    for prov in chain:
        if prov == "placeholder":
            return placeholder(prompt, size), "placeholder", "pillow"
        model = st.get("keyframe_model") if prov == first else None
        with timed() as t:
            try:
                if prov == "cloudflare":
                    model = model or "@cf/black-forest-labs/flux-2-klein-4b"
                    img = with_retries(lambda: P.cloudflare_image(prompt, seed=seed, size=size, refs=refs, model=model),
                                       what=f"cf {key}")
                else:
                    model = model or "flux"
                    img = with_retries(lambda: P.pollinations_image(prompt, seed=seed, size=size, model=model),
                                       what=f"pollinations {key}")
                status = "ok"
            except (QuotaExhausted, RuntimeError) as e:
                img, status = None, f"error: {e}"[:300]
        log_run(stage="keyframes", shot=key, provider=prov, model=model, seed=seed,
                params={"size": size, "prompt": prompt[:500], "refs": [str(r.name) for r in refs or []]}, latency_sec=t["sec"], status=status,
                cost_usd=0.0, list_price_usd=LIST_PRICE.get(prov, 0.0))
        if img:
            return img, prov, model
        print(f"    {key}: {prov} failed -> next provider")
    raise RuntimeError("unreachable")


def save_png(raw: bytes, path) -> None:
    import io
    Image.open(io.BytesIO(raw)).convert("RGB").save(path, "PNG")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--sheets-only", action="store_true")
    ap.add_argument("--candidates", type=int, default=0, help="explore N seeds per item into outputs/keyframes/candidates")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    d = ensure_dir(OUT / "keyframes")
    rep = StageReport("keyframes")

    def refs_for(shot):
        """Character sheets of the people in the shot; establishing shot s01 is the golden style
        reference for shots with no people, so places share one look."""
        if shot is None:
            return []
        if shot["characters"]:
            return [d / f"sheet_{c}.png" for c in shot["characters"][:2]]
        return [] if shot["id"] == sb["shots"][0]["id"] else [d / f"{sb['shots'][0]['id']}.png"]

    jobs = []
    for name, c in sb["characters"].items():
        body = (f"character reference sheet of {c['description']}, three views side by side: front, three-quarter, "
                f"profile, neutral plain background, full upper body")
        jobs.append((f"sheet_{name}", body, c["seed"], None))
    if not a.sheets_only:
        for s in sb["shots"]:
            jobs.append((s["id"], s["image_prompt"], shot_seed(sb, s), s))

    for key, body, seed, shot in jobs:
        refs = [r for r in refs_for(shot) if r.exists()]
        if a.only and key not in a.only:
            continue
        prompt = full_prompt(sb, body)
        if a.candidates:
            cd = ensure_dir(d / "candidates")
            for k in range(a.candidates):
                raw, prov, model = generate(sb, prompt, seed + 100 * k, key, refs)
                save_png(raw, cd / f"{key}_seed{seed + 100 * k}.png")
            continue
        out = d / f"{key}.png"
        st = sb["style"]
        h = input_hash(prompt, seed, st.get("keyframe_provider"), st.get("keyframe_model"), st.get("keyframe_size"),
                       [file_hash(r) for r in refs])
        if not a.force and is_fresh(out, h):
            rep.hit(key)
            continue
        raw, prov, model = generate(sb, prompt, seed, key, refs)
        save_png(raw, out)
        write_meta(out, h, provider=prov, model=model, seed=seed, prompt=prompt, refs=[r.name for r in refs])
        if prov == "placeholder":
            rep.fallback(key, "all image providers failed; placeholder card")
        rep.miss(key, f"via {prov}")
    rep.done()


if __name__ == "__main__":
    main()
