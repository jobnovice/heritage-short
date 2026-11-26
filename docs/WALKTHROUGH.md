# Walkthrough script (≤ 5 minutes)

Record the screen with QuickTime (File → New Screen Recording). Terminal font ≥ 16 pt. Have open: VS Code on the repo,
a terminal in the repo, the ship's-log page, and `outputs/final/thursday_9x16.mp4`.

**Before recording:** run `make plan` and check that it says `0 model call(s)`. If not, run `make film` first.

| Time | Show | Say (in your own words) |
|---|---|---|
| 0:00-0:30 | First 20 s of the 9:16 film | "This is ሐሙስ, Thursday: my uncle's story. In 1982 E.C. he broke his arm two days before his ship sailed for Massawa. The ship never came back. I didn't edit this by hand: it comes out of one file." |
| 0:30-1:30 | `storyboard.json`, then the mermaid diagram in README | "Everything is in `storyboard.json`: 12 shots, each with a reason, an Amharic line, an English subtitle, an image prompt and a camera move. It's validated against a JSON Schema before every run. Five stages read it: narration, keyframes, music, shots, assembly. Each output has a sidecar with a hash of exactly its inputs, including the stage's own code, so a rerun only remakes what changed. Every model call is a line in `runs.jsonl`." |
| 1:30-2:30 | `FAILURES.md` F7, then `EXPERIMENTS.md` E5 | **One hard decision.** "Gemini TTS was reading my English style instruction out loud on 8 of 11 lines, and only sometimes. I tried the documented short form and it still happened. I added two detectors, a duration guard and an ASR round trip that transcribes each take back and scores it against the script, and then removed in-text instructions entirely. I lost some control over delivery but got clean takes. It also cost a day's quota, which is why there's a model fallback chain." *(Alternative: F13/E16. Three viewers heard the narrator change between scenes although every check passed; I measured 112-174 Hz across separate takes and moved to one take for the whole script, split by a small dynamic program. Trade-off: editing one line re-records all 12.)* |
| 2:30-3:00 | Ship's-log page, voyage chart | "The music is composed in code in Ethiopian qenet: tizita for memory, ambassel for the fall, silence at the sinking, and the Massawa theme back in bati major for the rebirth." |
| 3:00-4:30 | **Live edit** (below) | "Now I change one shot and show that only that shot regenerates." |
| 4:30-5:00 | The regenerated shot in the new film | "One prompt changed, one model call, one shot remade. The rest came from cache. Thanks." |

## The live edit (3:00-4:30)
Use a **keyframe prompt**: Cloudflare is fast (~8 s) and doesn't spend the TTS quota.

1. In `storyboard.json`, shot **s03** (Massawa), change the end of `image_prompt`:
   `"... small boats, dreamlike and warm"` → `"... small boats, seagulls over the harbour, dreamlike and warm"`
2. Terminal:
   ```bash
   make plan          # shows: keyframes + s03 regenerate, shots ~ s03, 1 model call
   make film          # pause the recording during the ~3-4 min render if you like
   ```
3. Point at the console summary lines:
   ```
   [keyframes] regenerated=['s03'] cached=14
   [narration] regenerated=- cached=12
   [shots] regenerated=['s03'] cached=11
   ```
4. Show the evidence in the log: `grep '"s03"' runs.jsonl | tail -2` (one new `keyframes` call for `s03`).
5. Play the s03 moment in the new film (~0:15).

Afterwards: keep the change and commit it, or revert with `git checkout storyboard.json && make film`.

## Likely interview questions (practise these)
- *Why plain stages and not agents?* The pipeline is linear; the contract and the cache do the coordinating.
- *Walk through one experiment:* E12 (pose leaking through references) or E10 (ducking release, measured).
- *A failure and what you did:* F7 (spoken prompts) or F8 (per-model daily quota → fallback chain → F12 consistency).
- *What did your audience say and what changed?* Test 1 → year, Friday shot, cause of sinking, male voice, older uncle's face. Test 2 (sister + two cousins) → one-take narrator, s04 shows him falling, s10 one radio (DESIGN.md).
- *How is consent handled?* Telegram voice note after watching the film; recorded in ETHICS.md; name withheld; honest note on timing.
