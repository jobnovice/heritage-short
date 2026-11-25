# Failure journal

Each entry: what broke, what I tried, what fixed it. Newest at the bottom. Times are EAT.

## F1 - Homebrew FFmpeg has no `subtitles` or `drawtext` filter (2026-11-26 00:45)
- **Broke:** planned to burn subtitles with `-vf subtitles=` and the end card with `drawtext`. `ffmpeg -filters` on the Homebrew 8.x bottle lists neither (no libass / libfreetype).
- **Tried:** considered rebuilding FFmpeg with libass; too slow and a stranger cloning the repo would hit the same wall.
- **Fixed:** all text (subtitles, title, end card) is drawn with Pillow into transparent PNGs using bundled OFL Noto fonts (`assets/fonts/`) and composited with `overlay=enable='between(t,a,b)'`. Works on any FFmpeg build, and Ge'ez script renders correctly, which drawtext often gets wrong.

## F2 - Amharic glyphs rendered as boxes on the end card (00:48)
- **Broke:** the badge line "AI-GENERATED · በAI የተሠራ" was drawn with the Latin Noto Sans, so the Ge'ez part showed tofu boxes.
- **Fixed:** mixed-script lines use Noto Sans Ethiopic, which also covers basic Latin.

## F3 - Title card invisible: fading a single still frame (00:49)
- **Broke:** `fade=...:alpha=1` on a PNG input applies to its one frame at t=0 (alpha 0), and overlay then repeats that invisible frame.
- **Fixed:** feed the title as a looped stream (`-loop 1 -t 4.2 -framerate 24`) and let overlay pass through at EOF.

## F4 - Cache served a stale render after I fixed the renderer (00:50)
- **Broke:** after fixing F2/F3, `make radio` printed `cached=2` and produced the old, broken video. The input hash covered storyboard data and upstream outputs, but not the code that turns them into pixels.
- **Fixed:** `common.code_hash(module, ...)` hashes the stage's own source files into the cache key (assemble, cards, music). Verified: first rerun regenerated mix + render, second rerun `cached=2` in 0.0 s.
- **Lesson:** code is an input. A content-addressed cache that ignores code silently lies.

## F5 - Pollinations free tier: 402 FREE_LIMIT, watermark, weak style adherence (01:00)
- **Broke:** first sheet run: 2 of 3 reference sheets fell back to placeholder cards. Log shows `HTTP 402 FREE_LIMIT: 1 image every 45 seconds per IP`.
- **Tried:** blind retries (3 x backoff 2/4/8 s) are shorter than the 45 s window, so all three failed.
- **Fixed:** provider self-throttles to one call per 46 s and honours the `Retry after Ns` in the 402 body. Rerun: 3/3 sheets, but 487 s wall time for 3 images.
- **Still wrong:** `nologo=true` is ignored (pollinations.ai watermark in the corner), the gouache style block is ignored (results look like 3D renders), and the commander sheet shows three different men. Decision: move keyframes to Cloudflare Workers AI FLUX (the brief's route); Pollinations stays as the second link in the fallback chain.

## F6 - First keyed smoke test: 3 of 5 checks failed (01:20)
- **Gemini text returned an empty string.** `gemini-2.5-flash` spent the 20-token `maxOutputTokens` on hidden thinking. Fix: `thinkingConfig.thinkingBudget = 0` for these short, structured calls.
- **Gemini TTS `finishReason: OTHER`, no audio** for the one-word input "ሰላም". The same call with a full Amharic sentence works on both `gemini-3.8-flash-tts` and `gemini-2.5-flash-preview-tts`. Very short inputs are not a valid smoke test for TTS.
- **Cloudflare `flux-1-schnell` 400: "Additional or unevaluated properties '/seed'".** schnell's schema has no seed, so a keyframe could never be reproduced. Listed the account's models and switched to `@cf/black-forest-labs/flux-2-klein-4b` (Apache 2.0), which takes multipart form data with `seed` and up to four reference images.
- **Model drift:** the template defaulted to 2.5-era model ids. `make smoke` now prints the model list; the key also exposes the brief's `gemini-3.8-flash` and `gemini-3.8-flash-tts`, now the defaults.
- **Gemini 503 "high demand"** on `gemini-3.8-flash` during testing: transient, handled by `with_retries`.

## F7 - Gemini TTS reads the style instruction aloud (01:40)
- **Broke:** 8 of 11 narration takes were 17-19 s regardless of length (s05: 4 words, 17.5 s). An ASR round trip of s05 returned "Read this Amharic narration slowly and warmly... " followed by the Amharic line. The model spoke my English style prefix as part of the narration, on some lines and not others.
- **Tried 1:** Gemini's documented short form ("Say slowly and warmly, like a nephew telling his family an old story: <text>"). s02 came out clean, but s06 still spoke the prefix (ASR similarity 0.455).
- **Tried 2 (detection):** (a) a duration guard rejects a take longer than 1.3 s/word + 2 s and retries it; (b) `--verify` transcribes each take with gemini-2.5-flash and scores character similarity to the script. Clean takes score 0.84-0.97, spoken-prefix takes 0.37-0.46. But ASR is not enough on its own: on the old s05 take it *dropped* the English and scored 0.842. The duration guard is the more reliable detector, so I keep both.
- **Status:** see F8 for the quota wall hit in the same run.

## F8 - Gemini TTS free-tier quota exhausted mid-run (01:45)
- **Broke:** the regeneration run got HTTP 429 on 9 of 11 lines after 4 attempts each (404 s wall time). Each was logged as a fallback; the old takes were kept and the run did not crash.
- **Fix for F7 (02:30):** with `gemini-3.8-flash-lite-tts` the short prefix was *also* spoken (s01, s10). Root cause: any instruction inside the text can be read aloud. Removed the style prefix entirely (`style_instruction: ""`), so the model receives only the Amharic line. Every take now falls in a sane 3.6-6.0 s, and ASR similarity is 0.83-0.94 on most lines.
- **F8 continued:** the daily free quota is per model. `gemini-3.8-flash-tts` ran out first; added `voice.fallback_models` (3.8-flash-lite-tts, then 2.5-flash-preview-tts). After three regeneration rounds, all three models hit their daily limits. s05 and s08-s11 still have stale takes until the quota resets (midnight Pacific, about 11:00 EAT). Lesson: debugging prompts against a free-tier daily quota is expensive. I should have tested the prompt format on one line before regenerating all eleven.
- **ASR quirks:** gemini-2.5-flash returned empty transcripts once its own quota was gone, so verification moved to `gemini-3.5-transcribe`. That model transcribed the stale s08 take into Devanagari ("हमू सुवात मरकबू..."), phonetically close but in the wrong script. Similarity is now `None` when ASR fails, rather than a misleading 0.

## F9 - Addis AI: no public API docs found (02:50)
- **Broke:** web searches turned up only third-party skill listings (STT at `api.addisassistant.com/api/v2/stt`, an `x-api-key` header), not a TTS reference.
- **Tried:** probed `POST /api/v1/audio` with `{"text", "language": "am"}`. It returned 200 with a base64 44.1 kHz mono WAV in 4.5 s.
- **Fixed:** `providers.addis_tts` resamples to 24 kHz s16 so both providers feed the same pipeline. Risk noted: an undocumented endpoint can change without notice. Gemini stays in the fallback design.
