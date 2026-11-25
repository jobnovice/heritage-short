# Architecture

## One contract, five stages

```
                     schema/storyboard.schema.json
                                 │ validates (every stage, every run)
                                 ▼
                          storyboard.json  ◄── the only place prompts, seeds, lines, cues live
     ┌──────────────┬────────────┼─────────────┬──────────────┐
     ▼              ▼            ▼             ▼              │
 narration      keyframes      music         (timing)         │
 TTS per shot   sheets → shots qenet / ACE   cut picture      │
 Addis│Gemini   klein+refs     -Step / file  to the voice     │
     │              │            │                            │
     │              ▼            │                            │
     │            shots          │                            │
     │      Ken Burns │ Wan 2.2  │                            │
     └──────────┬───┴────────────┘                            │
                ▼                                             │
            assemble  ── mix (duck, -14 LUFS) ── subtitles ── title/end card ── 9:16 + 16:9
                │
                └─► runs.jsonl (one line per model call + one summary per stage)
```

| Stage | Reads from storyboard | Writes | Cache key (input hash) |
|---|---|---|---|
| `narration` | `voice.*`, `shots[].narration.am` | `outputs/narration/sNN.wav` + measured duration | provider, model, voice, style, line |
| `keyframes` | `style.*`, `characters.*`, `shots[].image_prompt/seed` | `outputs/keyframes/sheet_*.png`, `sNN.png` | full prompt, seed, provider, model, size, **hashes of reference images** |
| `music` | `music.*`, shot timing | `outputs/music/score.wav`, `sea.wav` | composer source code, cue list, seed, timing |
| `shots` | `shots[].motion`, timing | `outputs/shots/sNN.mp4` (1440² master) | stage code, keyframe file hash, source (Ken Burns move or Wan clip hash), duration |
| `assemble` | everything above, `title`, `end_card` | `outputs/final/*.mp4`, `subtitles.en.srt`, `timing.json` | stage code, upstream hashes, subtitle events, cards |

`script` (drafting the storyboard) was done with the coding agent and Gemini in conversation, not as a runtime stage: the
storyboard is a reviewed, committed artifact, and regenerating it on each run would make the film non-reproducible.

## Contracts
- **Schema** (`schema/storyboard.schema.json`, Draft 2020-12): 8-12 shots; each requires `reason`, `shot_size`,
  `duration_sec`, `image_prompt`, a `motion.camera` (so a Ken Burns fallback always exists) and bilingual narration.
- **Semantic checks** (`common._semantic_checks`): unique ids, characters exist, music cues anchor to real shots, and any
  `real_person` character must carry a `consent_ref`. A storyboard that fails either check stops the run before any call.
- **Timing contract:** shot length = `max(duration_sec, narration + lead_in + tail)`. The picture is cut to the voice, so
  editing one line re-times only what follows, and the narration meta file is the source of truth.

## Caching
Every output has a `.meta.json` sidecar holding the `input_hash` of exactly the inputs that affect it. A stage
regenerates an item only when the hash differs or the file is missing. Three rules came out of real failures:
1. **Code is an input** (FAILURES F4): deterministic stages hash their own source file.
2. **Upstream files are inputs by content**: keyframes hash their reference images, and shots hash the keyframe PNG, so
   changing a character sheet ripples to exactly the shots that use it.
3. **Seeds are not guarantees** (EXPERIMENTS E2): hosted FLUX returns different pixels for the same seed, so the
   cached file *is* the reproducible artifact. Regeneration happens only on purpose.

Each stage ends with a `stage_summary` line in `runs.jsonl` listing `regenerated` vs `cached` ids, which is the evidence
for "only that shot regenerated" in the walkthrough.

## Failure handling
- `with_retries`: 3 attempts, exponential backoff with jitter, for `RetryableError` (429 rate, 5xx, timeouts, a TTS take
  that is implausibly long).
- `QuotaExhausted` (daily 429, missing key) skips retries and goes straight to the fallback:

| Stage | Fallback chain |
|---|---|
| narration | `voice.provider` (Addis or Gemini) → Gemini model chain `3.8-flash-tts → 3.8-flash-lite-tts → 2.5-flash-preview-tts` → keep the previous take and log a fallback |
| keyframes | storyboard provider (Cloudflare klein) → Pollinations (self-throttled to 1/46 s) → a placeholder card with the prompt text |
| shots | Wan 2.2 clip (only if its manifest matches the current keyframe hash) → Ken Burns |
| music | `acestep`/`file` candidate → qenet composer (always available, deterministic) |

Nothing blocks the edit. A run always produces a film; the summary line says what was degraded.

## Quality gates
- **Narration:** a duration guard (> 1.3 s/word + 2 s gets rejected and retried) and an optional ASR round trip
  (`--verify`, similarity to the script, logged per line). Both exist because TTS read the style prompt aloud (F7).
- **Mix:** each stem is pre-normalised, the score ducked with `sidechaincompress`, and the master two-pass `loudnorm`ed;
  measured LUFS/TP is logged per run.
- **Text:** never generated by an image model. Pillow draws subtitles, the title and the end card with bundled fonts.

## Secrets
`.env` (gitignored) holds keys; `.env.example` documents them. No key is logged: `runs.jsonl` stores model, params,
seed, latency, status and cost, never request headers.
