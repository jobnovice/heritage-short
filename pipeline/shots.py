"""Stage: moving shots. One square 1440x1440 24 fps clip per shot at its timed duration.

    python -m pipeline.shots [--only s05]

For each shot:
  1. if motion.use_video and a Wan 2.2 clip for *this exact keyframe* exists in outputs/clips/<id>.mp4
     (made by notebooks/wan22_kaggle.py, whose manifest records the keyframe hash), use it, looping
     or holding the last frame to fill the duration;
  2. otherwise a deterministic Ken Burns move (FFmpeg zoompan) chosen by motion.camera.
Square masters are center-cropped to 9:16 and 16:9 in assembly, so prompts keep subjects centered.
"""
from __future__ import annotations

import argparse
import json
import sys

from .common import (OUT, StageReport, code_hash, ensure_dir, ffmpeg, file_hash, input_hash, is_fresh,
                     load_storyboard, log_run, probe_duration, shot_timing, timed, write_meta)

S = 1440
FPS = 24
MOVES = {  # zoompan expressions; on = output frame number, d = total frames
    "push_in":   ("1.0+0.12*on/{d}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "pull_out":  ("1.12-0.12*on/{d}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "pan_left":  ("1.12", "(iw-iw/zoom)*(1-on/{d})", "ih/2-(ih/zoom/2)"),
    "pan_right": ("1.12", "(iw-iw/zoom)*on/{d}", "ih/2-(ih/zoom/2)"),
    "tilt_up":   ("1.12", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-on/{d})"),
    "tilt_down": ("1.12", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*on/{d}"),
    "static":    ("1.03+0.02*on/{d}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),  # near-still breathing
}


def ken_burns(img, out, camera: str, dur: float) -> None:
    d = int(round(dur * FPS))
    z, x, y = (e.format(d=d) for e in MOVES[camera])
    # upscale first so zoompan's integer pixel steps don't jitter
    ffmpeg("-loop", "1", "-i", str(img), "-vf",
           f"scale={S * 2}:{S * 2}:flags=lanczos,zoompan=z='{z}':x='{x}':y='{y}':d={d}:s={S}x{S}:fps={FPS},"
           f"format=yuv420p", "-frames:v", str(d), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out))


def from_clip(clip, out, dur: float) -> None:
    """Fit a ~5 s Wan clip to the shot: trim the weak first 0.25 s, slow slightly, hold the last frame."""
    cd = probe_duration(clip) - 0.25
    speed = min(1.0, max(0.75, cd / dur))  # slow down at most 25%
    ffmpeg("-ss", "0.25", "-i", str(clip), "-vf",
           f"setpts=PTS/{speed},scale={S}:{S}:force_original_aspect_ratio=increase,crop={S}:{S},fps={FPS},"
           f"tpad=stop_mode=clone:stop_duration={dur},format=yuv420p",
           "-t", f"{dur}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out))


def shot_key(kf_hash: str, source: str, dur: float) -> str:
    return input_hash(code_hash(sys.modules[__name__]), kf_hash, source, dur)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    d = ensure_dir(OUT / "shots")
    rep = StageReport("shots")
    timing = {t["id"]: t for t in shot_timing(sb)}
    manifest_p = OUT / "clips" / "manifest.json"
    manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else {}
    me = code_hash(sys.modules[__name__])
    for s in sb["shots"]:
        if a.only and s["id"] not in a.only:
            continue
        kf = OUT / "keyframes" / f"{s['id']}.png"
        if not kf.exists():
            raise SystemExit(f"missing keyframe {kf}: run `make keyframes` first")
        dur = timing[s["id"]]["duration"]
        kf_h = file_hash(kf)
        clip = OUT / "clips" / f"{s['id']}.mp4"
        use_clip = s["motion"].get("use_video") and clip.exists() and manifest.get(s["id"], {}).get("keyframe_hash") == kf_h
        source = f"wan:{file_hash(clip)}" if use_clip else f"kenburns:{s['motion']['camera']}"
        out = d / f"{s['id']}.mp4"
        h = shot_key(kf_h, source, dur)
        if is_fresh(out, h):
            rep.hit(s["id"])
            continue
        if s["motion"].get("use_video") and not use_clip:
            rep.fallback(s["id"], "no Wan clip for this keyframe; Ken Burns")
        with timed() as t:
            (from_clip(clip, out, dur) if use_clip else ken_burns(kf, out, s["motion"]["camera"], dur))
        log_run(stage="shots", shot=s["id"], provider="ffmpeg" if not use_clip else "wan2.2(kaggle)+ffmpeg",
                model="zoompan" if not use_clip else manifest[s["id"]].get("model", "Wan2.2-TI2V-5B"),
                params={"camera": s["motion"]["camera"], "duration": dur}, latency_sec=t["sec"], status="ok",
                cost_usd=0.0, gpu_min=manifest.get(s["id"], {}).get("gpu_min", 0) if use_clip else 0)
        write_meta(out, h, source=source, duration_sec=dur)
        rep.miss(s["id"], source)
    rep.done()


if __name__ == "__main__":
    main()
