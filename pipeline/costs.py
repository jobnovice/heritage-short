"""Summarise runs.jsonl into the measured tables in COSTS.md (between the AUTO markers).

    python -m pipeline.costs
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict

from .common import ROOT, RUNS

# List-price equivalents (USD) if the same work were done on paid tiers; sources in COSTS.md.
LIST_PRICE = {
    ("keyframes", "cloudflare"): 0.0011,      # per 1024² image, Workers AI neuron pricing estimate
    ("narration", "gemini"): 0.0015,         # per line (~100 chars) at paid TTS rates
    ("narration", "addis"): 0.0,             # unknown public price
    ("narration_verify", "gemini"): 0.0002,  # per short audio transcription
}


def main():
    rows = [json.loads(l) for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip()]
    calls = [r for r in rows if r.get("kind") != "stage_summary" and r.get("stage") != "smoke"]
    g = defaultdict(list)
    for r in calls:
        g[(r.get("stage"), r.get("provider"), r.get("model"))].append(r)
    lines = ["| stage | provider | model | calls | ok | errors | median latency s | total s | GPU min | list-price USD |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for (stage, prov, model), rs in sorted(g.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        lat = [r["latency_sec"] for r in rs if isinstance(r.get("latency_sec"), (int, float))]
        ok = sum(1 for r in rs if r.get("status") == "ok")
        err = len(rs) - ok
        gpu = sum(r.get("gpu_min", 0) or 0 for r in rs)
        price = LIST_PRICE.get((stage, prov), 0.0) * ok
        lines.append(f"| {stage} | {prov} | {model} | {len(rs)} | {ok} | {err} | "
                     f"{statistics.median(lat) if lat else 0:.2f} | {sum(lat):.1f} | {gpu:.1f} | {price:.4f} |")
    summaries = [r for r in rows if r.get("kind") == "stage_summary"]
    lines += ["", f"Total logged model/tool calls: {len(calls)} (+{len(summaries)} stage summaries). "
              f"Actual spend: $0.00 (all free tiers)."]
    errs = defaultdict(int)
    for r in calls:
        s = str(r.get("status", ""))
        if s != "ok":
            key = "429 quota/rate" if "429" in s else "rejected_too_long" if "too_long" in s else \
                  "402 free limit" if "402" in s else "flagged (3030)" if "flagged" in s else "other"
            errs[key] += 1
    lines += ["", "| failure class | count |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(errs.items())]
    p = ROOT / "COSTS.md"
    text = p.read_text(encoding="utf-8")
    a, b = "<!-- AUTO:START -->", "<!-- AUTO:END -->"
    text = text[: text.index(a) + len(a)] + "\n" + "\n".join(lines) + "\n" + text[text.index(b):]
    p.write_text(text, encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
