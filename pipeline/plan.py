"""`make plan`: predict what `make film` would regenerate, without calling a single model.

Like `terraform plan` for a film. Uses the same key functions the stages use, then propagates
staleness downstream (sheet -> shots that reference it -> clips -> edit; narration -> timing -> music
and that shot's clip -> edit). Exit code 1 if anything would regenerate (handy in CI).
"""
from __future__ import annotations

import sys

from . import keyframes as K
from . import narration as N
from . import shots as SH
from .common import OUT, file_hash, is_fresh, load_storyboard, read_meta, shot_timing

G, Y, R, D = "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def plan(sb: dict) -> dict:
    res = {"narration": {}, "keyframes": {}, "shots": {}, "music": None, "edit": None}
    for s in sb["shots"]:
        out = OUT / "narration" / f"{s['id']}.wav"
        res["narration"][s["id"]] = "cached" if is_fresh(out, N.narration_key(sb, s)) else "regenerate"

    stale_refs = set()
    for key, body, seed, shot in K.jobs(sb):
        refs = [r for r in K.refs_for(sb, shot) if r.exists()]
        if any(r.name.replace("ref_", "sheet_") in stale_refs for r in refs):
            res["keyframes"][key] = "regenerate (reference sheet changes)"
        else:
            fresh = is_fresh(OUT / "keyframes" / f"{key}.png", K.job_hash(sb, K.full_prompt(sb, body), seed, refs))
            res["keyframes"][key] = "cached" if fresh else "regenerate"
        if key.startswith("sheet_") and res["keyframes"][key] != "cached":
            stale_refs.add(f"{key}.png")

    timing = {t["id"]: t for t in shot_timing(sb)}
    for s in sb["shots"]:
        sid = s["id"]
        if res["keyframes"][sid] != "cached":
            res["shots"][sid] = "regenerate (new keyframe)"
        elif res["narration"][sid] != "cached":
            res["shots"][sid] = "maybe (re-timed if the new line is longer than duration_sec)"
        else:
            kf = OUT / "keyframes" / f"{sid}.png"
            src = read_meta(OUT / "shots" / f"{sid}.mp4").get("source", f"kenburns:{s['motion']['camera']}")
            if not src.startswith("wan:"):
                src = f"kenburns:{s['motion']['camera']}"
            fresh = kf.exists() and is_fresh(OUT / "shots" / f"{sid}.mp4", SH.shot_key(file_hash(kf), src, timing[sid]["duration"]))
            res["shots"][sid] = "cached" if fresh else "regenerate"
    any_narr = any(v != "cached" for v in res["narration"].values())
    res["music"] = "maybe (re-timed)" if any_narr else ("cached" if (OUT / "music" / "score.wav").exists() else "regenerate")
    upstream = any(v != "cached" for st in ("narration", "keyframes", "shots") for v in res[st].values())
    res["edit"] = "regenerate (mix + both renders)" if upstream else "cached (assemble re-checks titles/cards)"
    return res


def main():
    sb = load_storyboard()
    res = plan(sb)
    calls = 0
    for stage in ("narration", "keyframes", "shots"):
        print(f"\n{stage}:")
        for k, v in res[stage].items():
            c = G if v == "cached" else (Y if v.startswith("maybe") else R)
            if v.startswith("regenerate") and stage != "shots":
                calls += 1
            print(f"  {c}{'=' if v == 'cached' else '~' if v.startswith('maybe') else '+'} {k:<20} {v}{D}")
    print(f"\nmusic: {res['music']}\nedit:  {res['edit']}")
    print(f"\nPlan: {calls} model call(s) would be made. Nothing has been called.")
    sys.exit(1 if calls else 0)


if __name__ == "__main__":
    main()
