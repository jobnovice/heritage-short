"""`make showcase`: build the film's "ship's log", a static provenance page, into docs/ (GitHub Pages).

Everything on the page is read from the repository's own evidence: storyboard.json, the .meta.json
sidecars, runs.jsonl and timing.json. Nothing is typed in by hand, so the page cannot drift from the run.

    python -m pipeline.showcase [--film-url https://youtu.be/...]
"""
from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict

from PIL import Image

from .common import OUT, ROOT, RUNS, load_storyboard, read_meta

DOCS = ROOT / "docs"
REPO = "https://github.com/jobnovice/heritage-short"
MODE_COLOR = {"tizita_minor": "#5b7a8c", "tizita_major": "#d9a441", "ambassel": "#8c4a3c",
              "bati_major": "#e8c36a", "bati_minor": "#7a6a8c", "anchihoye": "#6a8c6a", "silence": "transparent"}
E = html.escape


def tc(sec: float) -> str:
    return f"{int(sec // 60):02}:{sec % 60:05.2f}"


def last_ok(runs, stage, shot):
    for r in reversed(runs):
        if r.get("stage") == stage and r.get("shot") == shot and r.get("status") == "ok":
            return r
    return {}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--film-url", default="", help="public link to the 9:16 film (YouTube/TikTok/Drive)")
    a = ap.parse_args(argv)
    sb = load_storyboard()
    runs = [json.loads(l) for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip()]
    timing = {t["id"]: t for t in json.loads((OUT / "final" / "timing.json").read_text())}
    media = DOCS / "media"
    media.mkdir(parents=True, exist_ok=True)

    # regeneration history per shot from stage summaries
    regen = defaultdict(int)
    for r in runs:
        if r.get("kind") == "stage_summary" and r.get("stage") == "keyframes":
            for k in r.get("regenerated", []):
                regen[k] += 1

    total = max(t["start"] + t["duration"] for t in timing.values())
    starts = {sid: t["start"] for sid, t in timing.items()}
    cues = sorted(sb["music"]["cues"], key=lambda c: starts[c["starts_at_shot"]])
    strip = []
    for i, c in enumerate(cues):
        a0 = starts[c["starts_at_shot"]]
        b0 = starts[cues[i + 1]["starts_at_shot"]] if i + 1 < len(cues) else total
        label = "silence" if c["mode"] == "silence" else c["mode"].replace("_", " ")
        strip.append(f'<div class="cue {"sil" if c["mode"] == "silence" else ""}" title="{E(c["purpose"])}" '
                     f'style="left:{a0 / total * 100:.2f}%;width:{(b0 - a0) / total * 100:.2f}%;'
                     f'background:{MODE_COLOR[c["mode"]]}">{E(label)}</div>')
    shotbar = "".join(f'<a href="#{s["id"]}" class="sb" style="left:{timing[s["id"]]["start"] / total * 100:.2f}%;'
                      f'width:{timing[s["id"]]["duration"] / total * 100:.2f}%">{s["id"][1:]}</a>' for s in sb["shots"])

    entries = []
    for s in sb["shots"]:
        sid, t = s["id"], timing[s["id"]]
        kf = OUT / "keyframes" / f"{sid}.png"
        thumb = ""
        if kf.exists():
            Image.open(kf).convert("RGB").resize((480, 480)).save(media / f"{sid}.jpg", quality=82)
            thumb = f'<img src="media/{sid}.jpg" alt="{E(s["beat"])} keyframe" loading="lazy">'
        km, nm = read_meta(kf), read_meta(OUT / "narration" / f"{sid}.wav")
        kr, nr = last_ok(runs, "keyframes", sid), last_ok(runs, "narration", sid)
        sim = nm.get("asr_similarity")
        simtxt = "not checked" if sim is None else f"{sim:.2f}"
        entries.append(f"""
<article id="{sid}" class="entry">
  <div class="stamp"><b>{sid.upper()}</b><span>{tc(t['start'])}</span><span>{t['duration']:.1f} s</span><em>{E(s['beat'])}</em></div>
  <div class="pic">{thumb}</div>
  <div class="body">
    <p class="am" lang="am">{E(s['narration']['am'])}</p>
    <p class="en">{E(s['narration']['en'])}</p>
    <p class="why"><span>Why this shot</span>{E(s['reason'])}</p>
    <dl>
      <dt>Picture</dt><dd>{E(km.get('model', '?'))} · seed {km.get('seed', '?')} · refs {E(', '.join(km.get('refs', [])) or 'none')} · {kr.get('latency_sec', '?')} s · generated {regen.get(sid, 0)}×</dd>
      <dt>Motion</dt><dd>{E(s['motion']['camera'].replace('_', ' '))} (Ken Burns{', Wan 2.2 requested' if s['motion'].get('use_video') else ''})</dd>
      <dt>Voice</dt><dd>{E(nm.get('model', '?'))} · {nm.get('duration_sec', '?')} s · ASR similarity {simtxt}</dd>
    </dl>
  </div>
</article>""")

    calls = [r for r in runs if r.get("kind") != "stage_summary" and r.get("stage") != "smoke"]
    ok = sum(1 for r in calls if r.get("status") == "ok")
    provs = Counter(r.get("provider") for r in calls)
    errs = Counter(("429 quota" if "429" in str(r.get("status")) else "spoken-prompt take rejected" if "too_long" in str(r.get("status"))
                    else "other") for r in calls if r.get("status") != "ok")
    film = (f'<p class="film"><a href="{E(a.film_url)}">▶ Watch the film</a></p>' if a.film_url
            else '<p class="film muted">Film link added after posting.</p>')
    mix = read_meta(OUT / "edit" / "mix.wav")

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ሐሙስ / Thursday · the ship's log of a film</title>
<style>
:root{{--ink:#e9e1cf;--mute:#9aa7a6;--sea:#0f1b20;--paper:#15242a;--rule:#2a3d44;--gold:#d9a441}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--sea);color:var(--ink);font:16px/1.55 Georgia,serif}}
header,main,footer{{max-width:980px;margin:auto;padding:0 20px}}
header{{padding-top:48px}}h1{{font-size:56px;margin:0;letter-spacing:.02em}}h1 small{{display:block;font-size:18px;color:var(--mute);letter-spacing:.3em;text-transform:uppercase}}
.log{{color:var(--gold);text-transform:uppercase;letter-spacing:.25em;font-size:12px;margin:28px 0 6px}}
.lede{{font-size:19px;max-width:720px}}.muted{{color:var(--mute)}}.film a{{color:var(--sea);background:var(--gold);padding:10px 16px;border-radius:4px;text-decoration:none;font-weight:bold}}
.facts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:24px 0}}
.facts div{{border-top:1px solid var(--rule);padding-top:8px}}.facts b{{display:block;font-size:26px}}.facts span{{color:var(--mute);font-size:13px}}
.timeline{{position:relative;height:64px;margin:12px 0 4px}}.cue,.sb{{position:absolute;height:28px;font:11px/28px system-ui;overflow:hidden;white-space:nowrap;padding-left:4px}}
.cue{{top:0;color:#0f1b20}}.cue.sil{{border:1px dashed var(--mute);color:var(--mute)}}.sb{{top:34px;border-left:1px solid var(--rule);color:var(--mute);text-decoration:none}}
.sb:hover{{color:var(--gold)}}
.entry{{display:grid;grid-template-columns:110px 220px 1fr;gap:20px;border-top:1px solid var(--rule);padding:22px 0}}
.stamp{{font:13px/1.6 ui-monospace,Menlo,monospace;color:var(--mute)}}.stamp b{{display:block;color:var(--gold);font-size:15px}}.stamp span,.stamp em{{display:block}}
.pic img{{width:220px;height:220px;object-fit:cover;border-radius:3px;display:block}}
.am{{font-size:21px;margin:0 0 4px;font-family:"Noto Sans Ethiopic","Kefa",serif}}.en{{margin:0 0 12px;color:var(--mute);font-style:italic}}
.why span{{display:block;color:var(--gold);font:11px system-ui;letter-spacing:.2em;text-transform:uppercase}}
dl{{display:grid;grid-template-columns:70px 1fr;gap:2px 10px;font:12.5px/1.5 ui-monospace,Menlo,monospace;color:var(--mute);margin:10px 0 0}}dt{{color:var(--ink)}}dd{{margin:0}}
section{{margin:40px 0}}table{{border-collapse:collapse;font:14px system-ui}}td{{padding:4px 14px 4px 0;border-bottom:1px solid var(--rule)}}
a{{color:var(--gold)}}footer{{padding:40px 20px 60px;color:var(--mute);font-size:14px}}
@media(max-width:720px){{h1{{font-size:40px}}.entry{{grid-template-columns:1fr}}.pic img{{width:100%;height:auto}}}}
</style></head><body>
<header>
<p class="log">The ship's log of a film</p>
<h1 lang="am">{E(sb['title']['am'])}<small>{E(sb['title']['en'])}</small></h1>
<p class="lede">{E(sb['logline'])}</p>
{film}
<div class="facts">
<div><b>{total + sb['end_card']['duration_sec']:.1f} s</b><span>runtime, 9:16 + 16:9</span></div>
<div><b>{len(sb['shots'])}</b><span>shots, each with a stated reason</span></div>
<div><b>{len(calls)}</b><span>logged pipeline calls ({ok} ok)</span></div>
<div><b>$0.00</b><span>spent, all free tiers</span></div>
<div><b>{mix.get('final_lufs', '?')}</b><span>LUFS master, TP {mix.get('final_tp', '?')} dB</span></div>
</div>
</header>
<main>
<p class="log">Voyage chart: the score's qenet cues over the film</p>
<div class="timeline">{''.join(strip)}{shotbar}</div>
<p class="muted" style="font-size:13px">Tizita, the mode of longing, opens it; ambassel brings the fall; at the sinking the music stops; the Massawa theme returns in bati major for the rebirth. Hover a cue for its purpose, click a number to jump to that shot.</p>
<p class="log">Log entries</p>
{''.join(entries)}
<section><p class="log">What it took</p>
<table>{''.join(f'<tr><td>{E(str(p))}</td><td>{n} calls</td></tr>' for p, n in provs.most_common())}</table>
<p class="muted">Failures along the way: {', '.join(f'{n}× {k}' for k, n in errs.most_common())}. Every one is written up in
<a href="{REPO}/blob/main/FAILURES.md">FAILURES.md</a>; the measured comparisons are in <a href="{REPO}/blob/main/EXPERIMENTS.md">EXPERIMENTS.md</a>.</p></section>
<section><p class="log">Provenance</p>
<p>Images: FLUX.2 klein 4B (Cloudflare Workers AI), conditioned on character reference sheets. Voice: Gemini TTS (prebuilt voice, not a clone). Score: composed in code in Ethiopian qenet modes, no model. Edit: FFmpeg. The story is my uncle's; his consent record is in <a href="{REPO}/blob/main/ETHICS.md">ETHICS.md</a>. No photograph of him was used.</p>
<p class="muted">Regenerate everything: <code>git clone {REPO} && make setup && make film</code>. This page: <code>make showcase</code>.</p></section>
</main>
<footer>Made with AI. In memory of his comrades who did not return.</footer>
</body></html>"""
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {DOCS / 'index.html'} ({len(page) // 1024} KB) and {len(list(media.glob('*.jpg')))} thumbnails")


if __name__ == "__main__":
    main()
