# Walkthrough script: second by second (target 4:45, hard limit 5:00)

Every row says what is on screen, exactly what you do with the mouse and keyboard, and what to say. The "Say" text
is a full suggestion sized to fit its time slot (about 2.5 words a second). Say it in your own words; don't read it.
One cut is planned: while `make film` renders (~8 min) you pause the recording.

---

## A. The night before / one hour before (not recorded)

| # | Do | Check |
|---|---|---|
| A1 | `cd ~/heritage-short && git status` | "nothing to commit, working tree clean" (commit or stash anything else first) |
| A2 | `make plan` | last line: `Plan: 0 model call(s) would be made.` If not, run `make film` and wait until it is 0. |
| A3 | `make test` | `21 passed` |
| A4 | Practise the live edit once (section D), then undo it: `git checkout storyboard.json && make film` | the plan is back to 0 calls |
| A5 | Check Cloudflare still answers: `make smoke` (look for the cloudflare line `ok`) | if it fails, use the fallback in section E |
| A6 | Say the whole script out loud once with a timer | under 5:00 |

## B. Set up the screen (5 minutes before recording)

1. **Do Not Disturb on** (Control Centre → Focus). Quit Telegram, Mail, Slack. Hide the Dock (Cmd+Option+D).
2. **Terminal:** font 18 pt (Cmd+Plus), window about half the screen, `cd ~/heritage-short`, then `clear`.
3. **VS Code** on the repo. Zoom in twice (Cmd+Plus). Open these files as tabs, in this order:
   `storyboard.json` · `README.md` (preview: Cmd+Shift+V) · `FAILURES.md` · `EXPERIMENTS.md` · `pipeline/narration.py`.
   Close every other tab and the left sidebar (Cmd+B) for space.
4. **Browser** with two tabs: tab 1 is the **ship's log**, https://jobnovice.github.io/heritage-short/; tab 2 is the
   **GitHub repo**, https://github.com/jobnovice/heritage-short.
5. **QuickTime Player:** open `outputs/final/thursday_9x16.mp4`, paused at 0:00, volume up.
6. **Microphone:** Cmd+Shift+5 → Options → Microphone: your mic (or the AirPods). Say a test sentence and play it back.
7. **Recording area:** Cmd+Shift+5 → "Record Entire Screen". Don't press Record yet.

Window switching during the take: **Cmd+Tab** between QuickTime, VS Code, Terminal and the browser. In VS Code,
**Ctrl+Tab** (or click the tab) between files. **Cmd+G** in a file = go to line.

---

## C. The recording

### 0:00-0:30 Open with the film (hook)

| Time | Screen | Do | Say |
|---|---|---|---|
| 0:00 | QuickTime, film at 0:00 | Press **Record** (in the Cmd+Shift+5 bar), then click into QuickTime and press **Space** to play | *(say nothing; let the title and the first line play)* |
| 0:00-0:12 | Title card ሐሙስ / Thursday, first shot (the ship) | Let it play | *(silent: the narration is the voice you hear)* |
| 0:12 | Film continues | Lower the volume halfway (or press Space to pause at ~0:14) | "This is ሐሙስ, Thursday. It's my uncle's story. In 1982 E.C. he was a sailor in the Ethiopian Navy." |
| 0:20 | Paused frame | Keep it paused | "He slipped and broke his arm two days before his ship sailed for Massawa. The ship never came back. He calls the day he heard the news the day he was born again." |
| 0:27 | | | "I didn't edit any of this by hand. It all comes out of one file." |

### 0:30-1:25 The architecture: one contract, five stages

| Time | Screen | Do | Say |
|---|---|---|---|
| 0:30 | VS Code, `storyboard.json` | Cmd+Tab to VS Code, click the `storyboard.json` tab. **Cmd+G → 165** (shot s03) | "This is that file, `storyboard.json`. Here's one shot, s03." |
| 0:35 | s03 block visible (lines 165-182) | Move the mouse slowly down the block: `reason`, `image_prompt`, `motion.camera`, `narration.am`, `narration.en` | "Every shot has a reason it exists, an image prompt, a camera move, the Amharic line and its English subtitle. It's validated against a JSON Schema before every run, so a broken storyboard never reaches a model." |
| 0:48 | `storyboard.json` top | **Cmd+G → 44** (the `voice` block), point at `"take": "single"` (line 55) | "The voice, the music and the characters are in here too. I'll come back to this `take` setting." |
| 0:55 | README preview, the diagram | Click the `README.md` preview tab and scroll to **How the studio works** (the mermaid diagram) | "Five stages read that one file: narration, keyframes, music, shots, and assembly." |
| 1:02 | Diagram | Trace with the mouse: storyboard → narration → shots → assemble | "The narration comes first because the picture is cut to the voice: each shot lasts as long as its line plus a little air." |
| 1:10 | Diagram, `runs.jsonl` box | Point at the dotted `runs.jsonl` box | "Every output has a sidecar with a hash of exactly the inputs that made it, including the stage's own code. So a rerun only remakes what changed, and every model call is one line in `runs.jsonl`. I'll prove that live in a minute." |

### 1:25-2:25 One hard decision: the narrator who changed between scenes (F13 / E16)

| Time | Screen | Do | Say |
|---|---|---|---|
| 1:25 | `FAILURES.md` | Click the tab, **Cmd+G → 68** (F13) | "The hardest decision came from my user test. I showed the near-final cut to my sister and two cousins." |
| 1:32 | F13 text | Highlight the first bullet with the mouse | "All three said, independently, that the narrator's voice changed too much between scenes. And every automatic check had passed: same model, same voice, and a speech-recognition check said the words were right." |
| 1:44 | `EXPERIMENTS.md` | Click the tab, **Cmd+G → 121** (E16), point at "Measured before" | "So I measured it. Each line was a separate TTS call, and the pitch swung from 112 to 174 hertz between lines. It really was a different performance every time." |
| 1:56 | E16 "Change" and "Splitting" bullets | Point at each bullet as you mention it | "The fix: voice the whole script in one call, one performance, and cut it back into lines. Cutting at the longest silences failed, because pauses inside a line are as long as pauses between lines." |
| 2:06 | `pipeline/narration.py` | Click the tab, **Cmd+G → 125** (`split_take`) | "So this function uses a small dynamic program: it picks the cuts whose pieces best match each line's expected length. Pitch now stays within 96 to 135 hertz, and the drop follows the story." |
| 2:17 | Same | Point at the docstring | "The trade-off: editing one line now re-records all twelve. It's still one call, but I gave up per-line retakes for a consistent voice." |

*(Backup if you'd rather tell the older story: F7 at `FAILURES.md` line 36, where Gemini read my style instruction aloud on 8 of 11 lines, then E5. Same slot, same length.)*

### 2:25-2:50 The music and the evidence page

| Time | Screen | Do | Say |
|---|---|---|---|
| 2:25 | Browser, ship's log | Cmd+Tab to the browser, tab 1. Scroll slowly from the top to the voyage chart | "The score isn't generated by a model. It's composed in code in Ethiopian qenet modes: tizita, the mode of longing, for memory; ambassel for the fall; silence at the sinking; and the Massawa theme back in bati major for the rebirth." |
| 2:40 | Ship's log, shot cards | Scroll through two or three shot cards | "This page is generated from the run's own logs: every shot with the model, seed and checks that made it." |

### 2:50-4:30 Live edit: change one shot, regenerate only that shot

| Time | Screen | Do | Say |
|---|---|---|---|
| 2:50 | VS Code, `storyboard.json` | Cmd+Tab to VS Code, `storyboard.json` tab, **Cmd+G → 171** | "Now the live part. I'll change one shot and show that only that shot is remade." |
| 2:55 | Line 171, s03 `image_prompt` | Click just before `dreamlike and warm` at the end of the line | "This is the harbour at Massawa. I'll add seagulls." |
| 3:00 | Same | Type exactly: `seagulls over the harbour, ` (with the comma and the trailing space) so it reads `…small boats, seagulls over the harbour, dreamlike and warm`. **Cmd+S** | *(say it as you type)* "seagulls over the harbour." |
| 3:08 | Terminal | Cmd+Tab to Terminal, type `clear`, Enter, then `make plan`, Enter | "First, before spending anything, I ask the pipeline what it would do. Like terraform plan." |
| 3:12 | Plan output | Point at each line | "Keyframes: s03 regenerate. Shots: s03 regenerate. Narration: nothing, because no words changed. Music: cached. One model call. Nothing has been called yet." |
| 3:24 | Terminal | Type `make film`, Enter | "Now I run it." |
| 3:27 | First lines scroll | Wait until you see `[keyframes] regenerated=['s03'] cached=14` (about 10 s) | "There: one keyframe regenerated, s03, and fourteen from cache." |
| 3:38 | Narration and shots lines | Point at `[narration] regenerated=- cached=12` | "Narration: all twelve lines from cache." |
| 3:42 | Still rendering | **Pause the recording** (click the stop/pause icon in the menu bar; with Cmd+Shift+5, stop and start a second clip afterwards) | "The final render of both formats takes a few minutes, so I'll cut ahead." |
| *(cut)* | | Wait for the `[assemble]` lines and the prompt to return (~8 min) | |
| 3:45 | Terminal, finished output | **Resume recording**. Scroll up to the summary lines | "Done. Shots: s03 regenerated, the other eleven cached. The only new things are that one image, that one clip and the final mix." |
| 3:55 | Terminal | Type: `grep '"shot": "s03"' runs.jsonl \| tail -3`, Enter | "And here's the evidence in the log: one new keyframe call for s03, with its provider, seed and latency." |
| 4:08 | Finder → QuickTime | Cmd+Tab to QuickTime, File → Open Recent → `thursday_9x16.mp4` (reopen to load the new file), drag the playhead to **0:13** and press Space | "Here's the new shot." |
| 4:12-4:22 | New s03 with seagulls | Let it play about 8 s | *(let the narration play)* |

### 4:22-4:45 Close

| Time | Screen | Do | Say |
|---|---|---|---|
| 4:22 | Browser, tab 2 (GitHub repo) | Cmd+Tab to the browser, click tab 2 | "So: one prompt changed, one model call, one shot remade, everything else from cache, and every call on the record." |
| 4:32 | Repo README | Scroll a little to the film links | "The code, the experiments, the failures and the consent record are all in the repo, and the film is labelled as AI-made on the end card and on the platform." |
| 4:40 | | | "Thank you." |
| 4:45 | | **Stop recording** (menu-bar stop icon) | |

---

## D. The live edit at a glance (practise this)

```text
storyboard.json line 171, s03 image_prompt, before:
  "... palm trees, small boats, dreamlike and warm"
after:
  "... palm trees, small boats, seagulls over the harbour, dreamlike and warm"
```

Expected `make plan` (verified on the current repo):
```text
keyframes:
  + s03                  regenerate
shots:
  + s03                  regenerate (new keyframe)
music: cached
edit:  regenerate (mix + both renders)
Plan: 1 model call(s) would be made. Nothing has been called.
```
Expected `make film` summaries:
```text
[keyframes] regenerated=['s03'] cached=14 fallbacks=0
[narration] regenerated=- cached=12 fallbacks=0
[shots] regenerated=['s03'] cached=11 fallbacks=0
[music] regenerated=- cached=1
[assemble] regenerated=['mix', 'thursday_9x16.mp4', 'thursday_16x9.mp4']
```
If asked about video: "s09 and s10 are marked for Wan video clips; without a clip the pipeline falls back to a camera move and logs it, by design."

## E. If something goes wrong on camera

| Problem | What to do and say |
|---|---|
| Cloudflare error / slow keyframe | The pipeline falls back (Pollinations, then a placeholder card) and logs it. Say: "The image provider is down, so it's falling back, and that's logged too." Then show the `fallback` line in `runs.jsonl`. |
| `make plan` shows more than 1 call | You changed something else. Stop, `git diff storyboard.json`, undo the extra change, and re-record that part. |
| Typo in the JSON | `make film` stops at validation with the line number; say "and this is the schema catching it" and fix it. That's a good moment, not a bad one. |
| Over 5:00 | Cut the 2:25-2:50 music section (say one sentence about the score instead). |

## F. After recording

1. Trim the start and end in QuickTime: Edit → Trim (Cmd+T). If you made two clips, join them with Edit → Add Clip to End.
2. Export: File → Export As → 1080p. Upload to YouTube as **Unlisted** (or Google Drive with "anyone with the link"). Put the link in `docs/REPORT.md`.
3. Keep or undo the seagulls:
   - keep: `git add storyboard.json outputs && git commit -m "feat(storyboard): s03 seagulls (walkthrough live edit)"`
   - undo: `git checkout storyboard.json && make film`

## G. Likely interview questions (30-second answers)

- **Why plain stages and not agents?** The pipeline is linear. The JSON contract and the cache do the coordinating; agents would add failure modes, not capability.
- **Walk me through one experiment.** E16: hypothesis (separate takes drift), measured 112-174 Hz, change (one take plus a DP split), result 96-135 Hz, decision (consistency over per-line retakes). Or E12: pose leaking through full-body references.
- **A failure and what you did?** F7: the TTS read its instructions aloud; duration guard plus ASR round trip, then no in-text instructions. F8 → F12: per-model daily quota → fallback chain → mixed voices → pinned model plus a warning.
- **What did your audience say, and what changed?** Test 1 (family, first cut): the year, the Friday shot, why the ship sank, a male voice, the older uncle's face. Test 2 (sister and two cousins): a one-take narrator, s04 shows him falling, s10 one radio (DESIGN.md).
- **How is consent handled?** A Telegram voice note after he watched the film, following a script; recorded in ETHICS.md; his name withheld; the timing stated honestly; post-consent changes shown to him.
- **What would you do with more time?** Wan 2.2 clips for the three flagged shots, a web form so a relative can tell a story and get a storyboard back, and a LoRA vs reference-conditioning comparison.
