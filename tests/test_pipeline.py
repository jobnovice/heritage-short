"""Offline tests: no API keys, no network, no media generation beyond a short synthetic score."""
from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from pipeline import cards, common, keyframes as K, music as M, narration as N
from pipeline.assemble import write_srt


@pytest.fixture
def sb():
    return common.load_storyboard()


# ---------------------------------------------------------------- contract
def test_storyboard_is_valid_and_in_budget(sb):
    assert 8 <= len(sb["shots"]) <= 12
    assert all(len(s["reason"]) >= 10 for s in sb["shots"]), "every shot needs a stated reason"
    assert sum(s["duration_sec"] for s in sb["shots"]) <= 90


def _validate(doc):
    import jsonschema
    schema = json.loads(common.SCHEMA.read_text())
    return list(jsonschema.Draft202012Validator(schema).iter_errors(doc))


def test_schema_rejects_shot_without_reason(sb):
    bad = copy.deepcopy(sb)
    del bad["shots"][0]["reason"]
    assert _validate(bad)


def test_semantic_check_requires_consent_for_real_people(sb):
    bad = copy.deepcopy(sb)
    bad["characters"]["uncle_young"].pop("consent_ref")
    with pytest.raises(SystemExit):
        common._semantic_checks(bad)


def test_semantic_check_rejects_unknown_character(sb):
    bad = copy.deepcopy(sb)
    bad["shots"][0]["characters"] = ["nobody"]
    with pytest.raises(SystemExit):
        common._semantic_checks(bad)


# ---------------------------------------------------------------- caching: only the edited shot changes
def test_editing_one_line_changes_only_that_narration_key(sb):
    before = {s["id"]: N.narration_key(sb, s) for s in sb["shots"]}
    edited = copy.deepcopy(sb)
    edited["shots"][4]["narration"]["am"] += " ።"
    after = {s["id"]: N.narration_key(edited, s) for s in edited["shots"]}
    changed = [k for k in before if before[k] != after[k]]
    assert changed == [sb["shots"][4]["id"]]


def test_editing_one_prompt_changes_only_that_keyframe_key(sb):
    def keys(doc):
        return {key: K.job_hash(doc, K.full_prompt(doc, body), seed, [])
                for key, body, seed, _ in K.jobs(doc)}
    before = keys(sb)
    edited = copy.deepcopy(sb)
    edited["shots"][2]["image_prompt"] += ", gulls in the sky"
    after = keys(edited)
    assert [k for k in before if before[k] != after[k]] == [sb["shots"][2]["id"]]


def test_character_description_change_ripples_to_its_shots_only(sb):
    def keys(doc):
        return {key: K.job_hash(doc, K.full_prompt(doc, body), seed, []) for key, body, seed, _ in K.jobs(doc)}
    before = keys(sb)
    edited = copy.deepcopy(sb)
    edited["characters"]["uncle_now"]["description"] += ", reading glasses"
    changed = {k for k in before if before[k] != keys(edited)[k]}
    uses = {s["id"] for s in sb["shots"] if "{uncle_now}" in s["image_prompt"]}
    assert changed == uses | {"sheet_uncle_now"}


def test_cache_roundtrip(tmp_path):
    out = tmp_path / "x.wav"
    out.write_bytes(b"data")
    common.write_meta(out, "abc")
    assert common.is_fresh(out, "abc")
    assert not common.is_fresh(out, "abd")


def test_code_hash_changes_with_source(tmp_path, monkeypatch):
    import types
    f = tmp_path / "mod.py"
    f.write_text("a = 1\n")
    mod = types.SimpleNamespace(__file__=str(f))
    h1 = common.code_hash(mod)
    f.write_text("a = 2\n")
    assert common.code_hash(mod) != h1


# ---------------------------------------------------------------- timing
def test_picture_is_cut_to_the_voice(sb, tmp_path, monkeypatch):
    monkeypatch.setattr(common, "OUT", tmp_path)
    nd = tmp_path / "narration"
    nd.mkdir()
    first = sb["shots"][0]
    wav = nd / f"{first['id']}.wav"
    wav.write_bytes(b"")
    common.write_meta(wav, "h", duration_sec=20.0)
    t = common.shot_timing(sb)
    v = sb["voice"]
    assert t[0]["duration"] == pytest.approx(20.0 + v["lead_in_sec"] + v["tail_sec"])
    assert t[1]["duration"] == sb["shots"][1]["duration_sec"]  # no narration -> storyboard minimum
    assert t[1]["start"] == pytest.approx(t[0]["duration"])


# ---------------------------------------------------------------- text
def test_subtitles_fit_two_lines_of_32(sb):
    for s in sb["shots"]:
        for card in cards.wrap_subtitle(s["narration"]["en"]):
            assert len(card) <= 2 and all(len(line) <= 32 for line in card)


def test_srt_format(tmp_path):
    p = tmp_path / "s.srt"
    write_srt([(0.5, 2.25, ["Hello"]), (61.0, 63.5, ["two", "lines"])], p)
    txt = p.read_text()
    assert "00:00:00,500 --> 00:00:02,250" in txt and "00:01:01,000 --> 00:01:03,500" in txt


# ---------------------------------------------------------------- failure handling
class FakeResp:
    def __init__(self, code, text=""):
        self.status_code, self.text = code, text


@pytest.mark.parametrize("code,text,exc", [
    (429, "rate limited, slow down", common.RetryableError),
    (429, "Generate content requests per day limit exceeded on quota", common.QuotaExhausted),
    (503, "high demand", common.RetryableError),
    (400, "bad input", RuntimeError),
])
def test_http_errors_are_classified(code, text, exc):
    with pytest.raises(exc):
        common.classify_http(FakeResp(code, text))


def test_retries_then_gives_up_with_quota_exhausted(monkeypatch):
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        raise common.RetryableError("429")
    with pytest.raises(common.QuotaExhausted):
        common.with_retries(flaky, attempts=3)
    assert len(calls) == 3


def test_tts_duration_guard():
    four_words = "ቁርጭምጭሚቱ ተጣመመ፤ ክንዱም ተሰበረ።"
    assert N.max_plausible_sec(four_words) < 17.5  # the 17.5 s take that read the prompt aloud (F7) is rejected


# ---------------------------------------------------------------- music
def test_qenet_composer_is_deterministic_and_respects_silence(sb):
    timing = [{"id": s["id"], "start": i * 6.0, "duration": 6.0} for i, s in enumerate(sb["shots"])]
    a, _ = M.compose(sb, timing, seed=7)
    b, _ = M.compose(sb, timing, seed=7)
    assert np.array_equal(a, b)
    starts = {t["id"]: t["start"] for t in timing}
    silence = next(c for c in sb["music"]["cues"] if c["mode"] == "silence")
    nxt = sorted(starts[c["starts_at_shot"]] for c in sb["music"]["cues"] if starts[c["starts_at_shot"]] > starts[silence["starts_at_shot"]])[0]
    mid = int(((starts[silence["starts_at_shot"]] + 2.5 + nxt) / 2) * M.SR)
    assert np.abs(a[mid - 2000:mid + 2000]).max() < 0.02, "the loss cue should be (near) silent"


def test_single_take_split_ignores_pauses_inside_lines():
    """Lines of 2 s, 1 s, 3 s; line 3 has a 0.9 s pause inside it, longer than the 0.6 s between lines.
    'Cut at the longest gaps' would split line 3; the length-matching DP must not."""
    sr = 24000
    tone = lambda sec: (0.3 * np.sin(np.arange(int(sec * sr)) * 2 * np.pi * 150 / sr) * 32767).astype("<i2")
    gap = lambda sec: np.zeros(int(sec * sr), "<i2")
    pcm = np.concatenate([tone(2), gap(.6), tone(1), gap(.6), tone(1.5), gap(.9), tone(1.5)]).tobytes()
    segs = N.split_take(pcm, ["aaaaaaaaaaaaaaaaaaaa", "aaaaaaaaaa", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"], sr)
    durs = [len(s) / 2 / sr for s in segs]
    assert len(segs) == 3 and abs(durs[0] - 2.1) < .1 and abs(durs[1] - 1.1) < .1 and abs(durs[2] - 4.0) < .15


def test_single_take_key_changes_for_every_shot_when_one_line_changes(sb):
    sb["voice"]["take"] = "single"
    before = {s["id"]: N.narration_key(sb, s) for s in sb["shots"]}
    sb2 = copy.deepcopy(sb)
    sb2["shots"][3]["narration"]["am"] += " ።"
    after = {s["id"]: N.narration_key(sb2, s) for s in sb2["shots"]}
    assert len(set(before.values())) == 1 and all(before[k] != after[k] for k in before)
