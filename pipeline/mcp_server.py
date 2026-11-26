"""MCP server: lets any coding agent direct this film studio through four tools.

    python -m pipeline.mcp_server            # stdio transport

Claude Code / Claude Desktop config:
    {"mcpServers": {"heritage-short": {"command": "/abs/path/.venv/bin/python",
                                        "args": ["-m", "pipeline.mcp_server"], "cwd": "/abs/path/heritage-short"}}}

Design: an agent should *look before it spends*. `edit_shot` validates the whole storyboard before
writing and answers with the plan (what a render would now cost); `render` is the only tool that
calls models. `explain_shot` returns the provenance of one shot (the ship's-log entry as data).
"""
from __future__ import annotations

import copy
import json
import subprocess

import jsonschema
from mcp.server.mcpserver import MCPServer

from . import plan as PL
from .common import OUT, ROOT, SCHEMA, STORYBOARD, _semantic_checks, read_meta

server = MCPServer(name="heritage-short", title="Heritage Short film studio",
                   instructions="Edit storyboard.json shots, check the plan, then render. Rendering calls paid/quota'd models: "
                                "always read the plan first.")

EDITABLE = {"narration_am": ("narration", "am"), "narration_en": ("narration", "en"),
            "image_prompt": ("image_prompt",), "camera": ("motion", "camera"), "reason": ("reason",)}


def _load() -> dict:
    return json.loads(STORYBOARD.read_text(encoding="utf-8"))


def _check(sb: dict) -> list[str]:
    errs = [f"{'/'.join(map(str, e.path))}: {e.message}"
            for e in jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(sb)]
    if not errs:
        try:
            _semantic_checks(sb)
        except SystemExit as e:
            errs.append(str(e))
    return errs


@server.tool(description="Predict what a render would regenerate (no model is called).")
def plan() -> dict:
    sb = _load()
    errs = _check(sb)
    if errs:
        return {"valid": False, "errors": errs}
    res = PL.plan(sb)
    calls = sum(1 for st in ("narration", "keyframes") for v in res[st].values() if v.startswith("regenerate"))
    changed = {st: {k: v for k, v in res[st].items() if v != "cached"} for st in ("narration", "keyframes", "shots")}
    return {"valid": True, "model_calls": calls, "changed": changed, "music": res["music"], "edit": res["edit"]}


@server.tool(description="Provenance of one shot: storyboard entry, timing, models, seeds, ASR score.")
def explain_shot(shot_id: str) -> dict:
    sb = _load()
    shot = next((s for s in sb["shots"] if s["id"] == shot_id), None)
    if not shot:
        return {"error": f"no shot {shot_id}", "shots": [s["id"] for s in sb["shots"]]}
    timing = json.loads((OUT / "final" / "timing.json").read_text()) if (OUT / "final" / "timing.json").exists() else []
    km, nm = read_meta(OUT / "keyframes" / f"{shot_id}.png"), read_meta(OUT / "narration" / f"{shot_id}.wav")
    return {"shot": shot, "timing": next((t for t in timing if t["id"] == shot_id), None),
            "keyframe": {k: km.get(k) for k in ("provider", "model", "seed", "refs", "written_at")},
            "narration": {k: nm.get(k) for k in ("model", "duration_sec", "asr_similarity", "asr_text", "written_at")}}


@server.tool(description="Edit one field of one shot (narration_am, narration_en, image_prompt, camera, reason). "
                         "Validated before writing; returns the new plan.")
def edit_shot(shot_id: str, field: str, value: str) -> dict:
    if field not in EDITABLE:
        return {"error": f"field must be one of {list(EDITABLE)}"}
    sb = _load()
    new = copy.deepcopy(sb)
    shot = next((s for s in new["shots"] if s["id"] == shot_id), None)
    if not shot:
        return {"error": f"no shot {shot_id}"}
    *path, last = EDITABLE[field]
    node = shot
    for p in path:
        node = node[p]
    old, node[last] = node[last], value
    errs = _check(new)
    if errs:
        return {"written": False, "errors": errs}
    STORYBOARD.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"written": True, "old": old, "new": value, "plan": plan()}


@server.tool(description="Run the pipeline: target is one of radio, film, keyframes, narration. Calls models.")
def render(target: str = "film") -> dict:
    if target not in ("radio", "film", "keyframes", "narration"):
        return {"error": "target must be radio, film, keyframes or narration"}
    r = subprocess.run(["make", target], cwd=ROOT, capture_output=True, text=True, timeout=3600)
    summaries = [l for l in r.stdout.splitlines() if l.startswith("[")]
    return {"ok": r.returncode == 0, "stage_summaries": summaries, "stderr_tail": r.stderr[-800:]}


if __name__ == "__main__":
    server.run("stdio")
