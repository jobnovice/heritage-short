"""Stage: assembly (pure FFmpeg + Pillow, no AI, deterministic).

    python -m pipeline.assemble --radio     # radio cut: narration + score on black, English subtitles
    python -m pipeline.assemble             # final film in 9:16 and 16:9

Mix: voice is the spine. Each stem is brought to a working loudness first, the score is ducked under
the voice with sidechaincompress, the sea ambience sits underneath, then a two-pass loudnorm takes
the master to -14 LUFS / -1 dBTP.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

from . import cards
from .common import (OUT, code_hash, StageReport, ensure_dir, ffmpeg, file_hash, input_hash, is_fresh, load_storyboard,
                     log_run, read_meta, shot_timing, timed, write_meta)

FPS = 24


# ---------------------------------------------------------------- audio
def build_voice(sb, timing, total, path: Path) -> None:
    sr = 24000
    track = np.zeros(int((total + 1) * sr), dtype=np.int32)
    for t in timing:
        wav = OUT / "narration" / f"{t['id']}.wav"
        if not wav.exists():
            continue
        with wave.open(str(wav)) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.int32)
        j = int(t["voice_at"] * sr)
        track[j:j + len(x)] += x[: len(track) - j]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.clip(track, -32768, 32767).astype("<i2").tobytes())


def mix(sb, voice: Path, out: Path, total: float) -> dict:
    m = sb["music"]
    dk = m.get("duck", {})
    duck = (f"sidechaincompress=threshold={dk.get('threshold', 0.02)}:ratio={dk.get('ratio', 6)}:"
            f"attack={dk.get('attack_ms', 300)}:release={dk.get('release_ms', 1500)}")
    graph = (
        f"[0:a]aresample=48000,loudnorm=I=-16:TP=-2:LRA=9,asplit=2[vk][vm];"
        f"[1:a]aresample=48000,loudnorm=I=-23:TP=-4[mu];"
        f"[2:a]aresample=48000,volume=0.35[sea];"
        f"[mu][vk]{duck}[md];"
        f"[vm][md][sea]amix=inputs=3:normalize=0:duration=first,atrim=0:{total:.2f}[mix]"
    )
    pre = out.with_name("premix.wav")
    ffmpeg("-i", str(voice), "-i", str(OUT / "music" / "score.wav"), "-i", str(OUT / "music" / "sea.wav"),
           "-filter_complex", graph, "-map", "[mix]", "-ac", "2", str(pre))
    # two-pass loudnorm
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(pre), "-af",
                        "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    j = json.loads(r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1])
    ffmpeg("-i", str(pre), "-af",
           f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
           f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true",
           "-ar", "48000", str(out))
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    k = json.loads(r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1])
    return {"premix_lufs": float(j["input_i"]), "final_lufs": float(k["input_i"]), "final_tp": float(k["input_tp"])}


# ---------------------------------------------------------------- subtitles
def subtitle_events(sb, timing) -> list[tuple[float, float, list[str]]]:
    ev = []
    for s, t in zip(sb["shots"], timing):
        groups = cards.wrap_subtitle(s["narration"]["en"])
        span = t["narration_sec"] or max(1.5, t["duration"] - 1.0)
        per = span / len(groups)
        for i, g in enumerate(groups):
            a = t["voice_at"] + i * per
            ev.append((round(a, 2), round(a + per + (0.3 if i == len(groups) - 1 else 0), 2), g))
    return ev


def write_srt(events, path: Path) -> None:
    def ts(x):
        h, r = divmod(x, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{int(round((s % 1) * 1000)):03}"
    path.write_text("\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n" + "\n".join(lines) + "\n"
                              for i, (a, b, lines) in enumerate(events, 1)), encoding="utf-8")


# ---------------------------------------------------------------- picture
def render(sb, timing, aspect: str, audio: Path, out: Path, radio: bool, total_main: float) -> None:
    W, H = cards.ASPECTS[aspect]
    tmp = ensure_dir(OUT / "edit" / aspect)
    end_d = sb.get("end_card", {}).get("duration_sec", 3.5)
    ec = sb.get("end_card", {})
    cards.end_card_png(ec.get("lines_am", []), ec.get("lines_en", []), aspect, tmp / "end.png")
    cards.title_png(sb["title"]["am"], sb["title"]["en"], aspect, tmp / "title.png")
    events = subtitle_events(sb, timing)
    inputs, filt = [], []
    if radio:
        inputs += ["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={total_main:.2f}"]
        filt.append("[0:v]format=yuv420p[base]")
        n_in = 1
    else:
        for t in timing:
            inputs += ["-i", str(OUT / "shots" / f"{t['id']}.mp4")]
        n = len(timing)
        for i, t in enumerate(timing):
            filt.append(f"[{i}:v]trim=0:{t['duration']},setpts=PTS-STARTPTS,scale={max(W, H)}:{max(W, H)},"
                        f"crop={W}:{H},fps={FPS},format=yuv420p,setsar=1[v{i}]")
        filt.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fade=t=in:st=0:d=1.2,"
                    f"fade=t=out:st={total_main - 1.0:.2f}:d=1.0[base]")
        n_in = n
    # title over the opening, then subtitles
    inputs += ["-loop", "1", "-t", "4.2", "-framerate", str(FPS), "-i", str(tmp / "title.png")]
    filt.append(f"[{n_in}:v]format=rgba,fade=t=in:st=0.3:d=0.8:alpha=1,fade=t=out:st=3.2:d=0.8:alpha=1[ti];"
                f"[base][ti]overlay=0:0:eof_action=pass[o0]")
    idx, last = n_in + 1, "o0"
    for k, (a, b, lines) in enumerate(events):
        p = tmp / f"sub_{k:02}.png"
        cards.subtitle_png(lines, aspect, p)
        inputs += ["-i", str(p)]
        filt.append(f"[{last}][{idx}:v]overlay=0:0:enable='between(t,{a},{b})'[o{k + 1}]")
        idx, last = idx + 1, f"o{k + 1}"
    inputs += ["-loop", "1", "-t", f"{end_d}", "-framerate", str(FPS), "-i", str(tmp / "end.png")]
    filt.append(f"[{idx}:v]scale={W}:{H},fps={FPS},format=yuv420p,setsar=1,fade=t=in:st=0:d=0.6[end]")
    filt.append(f"[{last}]setsar=1[mainv];[mainv][end]concat=n=2:v=1:a=0[vout]")
    idx += 1
    inputs += ["-i", str(audio)]
    ffmpeg(*inputs, "-filter_complex", ";".join(filt), "-map", "[vout]", "-map", f"{idx}:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20" if not radio else "30", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
           "-metadata", "comment=AI-generated: images, voice and music made with AI models. See ETHICS.md",
           str(out))


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--radio", action="store_true")
    ap.add_argument("--aspect", choices=["9x16", "16x9"], nargs="*")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    timing = shot_timing(sb)
    total_main = timing[-1]["start"] + timing[-1]["duration"]
    end_d = sb.get("end_card", {}).get("duration_sec", 3.5)
    total = total_main + end_d
    edit, final = ensure_dir(OUT / "edit"), ensure_dir(OUT / "final")
    rep = StageReport("assemble")

    # audio (shared by both aspects and the radio cut)
    upstream = [read_meta(OUT / "narration" / f"{t['id']}.wav").get("input_hash") for t in timing]
    upstream.append(read_meta(OUT / "music" / "score.wav").get("input_hash"))
    mix_out = edit / "mix.wav"
    ah = input_hash("mix-v1", code_hash(sys.modules[__name__]), upstream, timing, sb["music"].get("duck"), total)
    if is_fresh(mix_out, ah):
        rep.hit("mix")
    else:
        build_voice(sb, timing, total, edit / "voice.wav")
        with timed() as t:
            lv = mix(sb, edit / "voice.wav", mix_out, total)
        write_meta(mix_out, ah, **lv)
        log_run(stage="assemble", provider="ffmpeg", model="mix", latency_sec=t["sec"], status="ok", cost_usd=0.0, **lv)
        rep.miss("mix", f"{lv['final_lufs']} LUFS, TP {lv['final_tp']} dB")
    events = subtitle_events(sb, timing)
    write_srt(events, final / "subtitles.en.srt")
    (final / "timing.json").write_text(json.dumps(timing, indent=2))

    targets = ["9x16"] if a.radio and not a.aspect else (a.aspect or ["9x16", "16x9"])
    for asp in targets:
        name = f"radio_cut_{asp}.mp4" if a.radio else f"thursday_{asp}.mp4"
        out = final / name
        shots_h = [] if a.radio else [read_meta(OUT / "shots" / f"{t['id']}.mp4").get("input_hash") for t in timing]
        if not a.radio and None in shots_h:
            raise SystemExit("missing shots: run `make shots` first")
        vh = input_hash("render-v1", code_hash(cards, sys.modules[__name__]), asp, a.radio, ah, shots_h, events, sb["title"], sb.get("end_card"))
        if is_fresh(out, vh):
            rep.hit(name)
            continue
        with timed() as t:
            render(sb, timing, asp, mix_out, out, a.radio, total_main)
        write_meta(out, vh, duration_sec=round(total, 2), sha=file_hash(out))
        log_run(stage="assemble", provider="ffmpeg", model="render", params={"aspect": asp, "radio": a.radio},
                latency_sec=t["sec"], status="ok", cost_usd=0.0, duration_sec=round(total, 2))
        rep.miss(name, f"{total:.1f}s")
    rep.done()


if __name__ == "__main__":
    main()
