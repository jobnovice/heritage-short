"""python -m pipeline.validate : schema + semantic validation, plus a duration/word budget report."""
from .common import load_storyboard


def main():
    sb = load_storyboard()
    shots = sb["shots"]
    en_words = sum(len(s["narration"]["en"].split()) for s in shots)
    am_words = sum(len(s["narration"]["am"].split()) for s in shots)
    min_total = sum(s["duration_sec"] for s in shots) + sb.get("end_card", {}).get("duration_sec", 3.5)
    lo, hi = sb.get("target_duration_sec", [60, 90])
    print(f"storyboard OK: {len(shots)} shots, {am_words} Amharic words / {en_words} English subtitle words, "
          f"minimum runtime {min_total:.0f}s (target {lo}-{hi}s)")
    if min_total > hi:
        raise SystemExit("minimum runtime already exceeds the target")


if __name__ == "__main__":
    main()
