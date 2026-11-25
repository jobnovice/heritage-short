# Experiments

Format: **hypothesis → change → result → decision**. Evidence lives in `runs.jsonl` (filter by `stage`) and in
the `.meta.json` sidecars under `outputs/`. Times are EAT, 26 Nov 2026.

---

### E1 - Keyless Pollinations FLUX is good enough for reference sheets
- **Hypothesis:** a keyless endpoint avoids account setup and is good enough for character sheets.
- **Change:** generated 3 sheets via Pollinations (`model=flux`, 1024²), then the same 3 via Cloudflare `flux-2-klein-4b`.
- **Result:** Pollinations: 487 s wall time for 3 images, because of the 1 img/45 s free limit plus 402 retries (F5); visible watermark despite `nologo=true`; the gouache style was ignored (3D-render look); the commander sheet showed three different faces. Klein: about 6-8 s per image and visibly painterly.
- **Decision:** Cloudflare klein is the primary keyframe provider; Pollinations is the second link of the fallback chain.

### E2 - A fixed seed makes klein reproducible
- **Hypothesis:** same prompt + same seed gives the same image (as the brief's glossary suggests).
- **Change:** called `flux-2-klein-4b` twice with seed=5 and an identical prompt (768²).
- **Result:** two different images (md5 `93da3e…` vs `a19b81…`, 420 507 vs 427 517 bytes). The API accepts `seed` but the output is not bit-reproducible.
- **Decision:** reproducibility comes from the **cache**, not from regeneration. Keyframes are stored with their prompt/seed/ref hashes in `.meta.json`, and a re-run only calls the model when those inputs change. Logged so nobody assumes a seed is a guarantee on hosted endpoints.

### E3 - Reference-image conditioning beats prompt-only consistency
- **Hypothesis:** passing the character sheet as `input_image_0` keeps the same face across shots better than repeating the text description.
- **Change:** one klein call with the `uncle_now` sheet as reference and a new scene prompt (sitting by a window with a book).
- **Result:** same grey hair, beard shape, face and shirt carried into a new composition and pose, in the painted style. With prompt text alone (E1) the identity drifted, even inside one sheet.
- **Decision:** `keyframes.py` passes each shot's character sheets as references (up to 2). People-free shots get `s01` as a golden style reference so the places share one look. Ref file hashes are part of the cache key.

### E4 - gemini-3.8-flash-tts paces Amharic differently from 2.5
- **Hypothesis:** the newer TTS model speaks at a similar rate.
- **Change:** the same s01 line on both models, same voice (Charon).
- **Result:** 10.05 s (3.8) vs 6.33 s (2.5). **Confounded:** that test still had the English style prefix in the text, which E5 later showed is sometimes spoken aloud, so part of the 3.8 length may be the prefix.
- **Decision:** inconclusive. To be rerun with the bare line once the 3.8 daily quota resets (~11:00 EAT).

### E5 - A style instruction inside the TTS text improves delivery
- **Hypothesis:** "Read this slowly and warmly…" before the line gives a calmer, better-paced read.
- **Change (a):** long prefix on all 11 lines. **(b):** Gemini's documented short form "Say slowly and warmly…:". **(c):** no prefix.
- **Result:** (a) 8/11 takes were 17-19 s regardless of length; ASR heard the English prefix spoken. (b) s06 still spoke it (ASR similarity 0.455), and with 3.8-lite so did s01 and s10. (c) every take 3.6-6.0 s, ASR similarity 0.63-0.94.
- **Decision:** no in-text instructions (`style_instruction: ""`). Voice choice carries the tone. Cost of learning this: about 30 TTS calls of daily quota (F7, F8).

### E6 - Gemini TTS vs Addis AI for Amharic narration
- **Hypothesis:** an Amharic-first model (Addis AI, suggested by colleagues) pronounces better than a 180-language model.
- **Change:** all 11 lines through Addis AI (`--provider addis --outdir narration_addis`), compared with the clean Gemini takes; both checked by ASR round trip.
- **Result (measured):**

  | | Gemini (no prefix, 2.5-flash-preview-tts) | Addis AI |
  |---|---|---|
  | Lines completed today | 7/11 clean (quota wall) | 11/11 |
  | Total speech, 11 lines | n/a (mixed set) | 39.8 s |
  | Latency per line | ~6 s | ~4-6 s (67.8 s for 11 incl. ASR) |
  | ASR similarity (where ASR answered) | 0.63-0.94 (median ~0.87) | 0.60-0.90 (median ~0.84) |
  | Deterministic? | not tested | no: s01 3.98 s then 4.23 s on rerun |

- **Caveat:** the ASR judge is itself a Gemini model, which may favour Gemini audio. ASR answered only 7/11 Addis lines before its own quota ran out.
- **Decision (provisional):** Addis AI narrates the radio cut because it is the only complete, single-voice set. Final choice by a native-speaker listen: [FILL IN after listening: which voice, and why].

### E7 - ASR round trip as an automatic narration QA
- **Hypothesis:** transcribing each take and comparing it with the script flags bad takes without a human.
- **Change:** `narration --verify`: Gemini transcription → character similarity (difflib), English words in an Amharic take cap the score at 0.5.
- **Result:** it caught spoken prefixes (0.37-0.48) and flagged s04 (0.63) and s02 (0.68-0.83, "እንቅልፍ" heard as "እንግልት"/"እንክብካቤው"). Blind spots: on one take ASR *dropped* the English and scored 0.84, and it wrote another take in Devanagari script.
- **Decision:** keep it as a cheap first filter next to the duration guard. A native speaker still has the last word.

### E8 - Code must be part of the cache key
- **Hypothesis:** hashing storyboard inputs and upstream outputs is enough for "only regenerate what changed".
- **Change:** fixed two renderer bugs (title fade, glyph font), then reran.
- **Result:** `cached=2` and a stale, still-broken video (F4). After adding `code_hash()` of the stage's source: regenerate once, then `cached=2` in 0.0 s.
- **Decision:** all deterministic stages (music, shots, assemble) hash their own source code.

### E9 - Score candidates: which qenet seed under the narration
- [TO RUN: `python -m pipeline.music --candidates 3`, listen at low volume under the radio cut, write which seed and why.]

### E10 - Ducking settings
- Starting point from the brief: threshold 0.02, ratio 6, attack 300 ms, release 1500 ms. Radio cut master: -14.09 LUFS, -1.0 dBTP.
- [TO RUN: compare release 1500 vs 800 ms by ear on phone + headphones; record the choice.]
