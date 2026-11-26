# Costs and measurements

Everything ran on free tiers from Ethiopia with no payment card. **Actual spend: $0.00.**
The table below is generated from `runs.jsonl` by `make costs`; do not edit it by hand.

## Measured, per stage and provider
<!-- AUTO:START -->
| stage | provider | model | calls | ok | errors | median latency s | total s | GPU min | list-price USD |
|---|---|---|---|---|---|---|---|---|---|
| assemble | ffmpeg | mix | 10 | 10 | 0 | 24.97 | 244.7 | 0.0 | 0.0000 |
| assemble | ffmpeg | render | 22 | 22 | 0 | 97.60 | 1960.3 | 0.0 | 0.0000 |
| benchmark | addis | addis_default | 6 | 6 | 0 | 4.21 | 25.8 | 0.0 | 0.0000 |
| benchmark | edge | edge_ameha | 6 | 6 | 0 | 2.81 | 30.6 | 0.0 | 0.0000 |
| keyframes | cloudflare | @cf/black-forest-labs/flux-1-schnell | 2 | 0 | 2 | 0.00 | 0.0 | 0.0 | 0.0000 |
| keyframes | cloudflare | @cf/black-forest-labs/flux-2-klein-4b | 58 | 56 | 2 | 6.87 | 453.9 | 0.0 | 0.0616 |
| keyframes | pollinations | flux | 8 | 6 | 2 | 3.06 | 499.9 | 0.0 | 0.0000 |
| music | qenet | qenet-composer-v1 | 11 | 11 | 0 | 5.88 | 55.8 | 0.0 | 0.0000 |
| narration | addis | addis-ai-tts-v1 | 22 | 22 | 0 | 3.91 | 88.5 | 0.0 | 0.0000 |
| narration | gemini | gemini-3.8-flash-tts | 58 | 16 | 42 | 17.88 | 1047.5 | 0.0 | 0.0240 |
| narration | gemini | gemini-3.8-flash-lite-tts | 26 | 6 | 20 | 17.98 | 319.0 | 0.0 | 0.0090 |
| narration | gemini | gemini-2.5-flash-preview-tts | 14 | 9 | 5 | 6.86 | 150.0 | 0.0 | 0.0135 |
| narration | gemini | gemini-3.1-flash-tts-preview | 25 | 24 | 1 | 6.57 | 234.9 | 0.0 | 0.0360 |
| narration_verify | gemini | gemini-2.5-flash | 34 | 29 | 5 | 3.88 | 85.1 | 0.0 | 0.0058 |
| narration_verify | gemini | gemini-3.5-transcribe | 46 | 27 | 19 | 2.98 | 129.5 | 0.0 | 0.0054 |
| shots | ffmpeg | zoompan | 55 | 55 | 0 | 3.55 | 228.3 | 0.0 | 0.0000 |

Total logged model/tool calls: 403 (+80 stage summaries). Actual spend: $0.00 (all free tiers).

| failure class | count |
|---|---|
| 402 free limit | 2 |
| 429 quota/rate | 81 |
| flagged (3030) | 2 |
| other | 6 |
| rejected_too_long | 7 |
<!-- AUTO:END -->

## Free-tier limits as actually found (26 Nov 2026)

| Provider | What I found | Evidence |
|---|---|---|
| Gemini API, TTS | Daily request cap **per model per project**; `gemini-3.8-flash-tts` stopped after 13 successful calls, `3.8-flash-lite-tts` after 6, `2.5-flash-preview-tts` after 9 | 429 `GenerateRequestsPerDayPerProjectPerModel-FreeTier` in runs.jsonl, FAILURES F8 |
| Gemini API, text | Occasional 503 "high demand" on `gemini-3.8-flash` | FAILURES F6 |
| Cloudflare Workers AI | `flux-2-klein-4b` ~6-8 s per 1024² image; daily neuron allowance not hit yet | runs.jsonl `stage=keyframes provider=cloudflare` |
| Pollinations.ai | 1 image / 45 s / IP, then HTTP 402 FREE_LIMIT; watermark | FAILURES F5 |
| Addis AI | 11 lines in ~45-68 s, no limit hit | runs.jsonl `provider=addis` |
| Local (M-series Mac) | qenet score ~3-8 s; Ken Burns per shot and assembly see table | runs.jsonl `provider=ffmpeg/qenet` |

## List-price equivalent
Estimated cost if the same calls were made on paid tiers (per-call rates in `pipeline/costs.py`): see the last column above.
Rates are estimates from public pricing pages at the time of writing; Addis AI publishes no price, so it is counted as 0.

## Frontier comparison
No frontier lane (Omni Flash / Nano Banana / Lyria 3.5) was available to this cohort key. [FILL IN if access is granted.]
