# ሐሙስ / Thursday: report
**The Heritage Short: B2W0 AI-Content Generation.** Repository: https://github.com/jobnovice/heritage-short ·
Ship's log: https://jobnovice.github.io/heritage-short/ · Film: [FILL IN 9:16 link] · [FILL IN 16:9 link]

## 1. What I set out to make, and for whom
An 83-second Amharic film with English subtitles about my maternal uncle. In 1982 E.C. he was a sailor in the Ethiopian
Navy; two days before his ship sailed for Massawa he slipped and broke his arm, and his commander, who loved him like a
son, told him to stay behind. The ship was sunk in an attack by Eritrean fighters that Thursday. He heard the news on
Friday, which he calls the day he was born again, and he is now a preacher whose message is "ሕይወትህን እግዚአብሔር ይምራው".

**Audience:** my family, especially cousins in Addis and abroad who know only fragments of the story, watching on a phone
after it is forwarded on Telegram. **Intent:** at the end they should feel how close he came (two days, one slip),
gratitude rather than triumph, and remember the comrades who did not return (DESIGN.md).

I chose a **days-of-the-week structure** (Tuesday the fall, Wednesday despair, Thursday the ship sails, Friday the news,
Today) over a chronological telling or a flash-forward to the sinking, because it puts the turn on one small human
moment and keeps the war at a distance.

## 2. What I learned from my audience
**User test 1 (first full cut):** family reviewers watching on their phones gave five notes, and each one changed the
storyboard (DESIGN.md table, commit `feat(storyboard): review round 1`). The radio-cut test I planned before it did not happen in time:
- the older uncle didn't look like the young one (lighter skin) → his reference sheet is now generated *from* the young uncle's face;
- "a random Tuesday and Thursday" → the year 1982 E.C. is stated in the first line;
- his own turning point was missing → a new Friday shot: "He calls it the day he was born again";
- the film should say why the ship sank → s09 names the attack (I had left it out to stay neutral; it is their story);
- the narrator should be a man → Gemini "Charon" (median pitch ≈ 150 Hz) replaced the Addis AI default voice (≈ 220 Hz).

A native-speaker pass caught a literal calque: "በመርከቡ ሆድ ውስጥ" (the belly of the ship) became "በመርከቡ ውስጥ".
My uncle watched the film before giving consent and asked for no changes.

**User test 2 (near-final cut):** my sister and two cousins, none of whom had worked on the film.
- **All three said the narrator's voice changed too much between scenes.** Every automatic check had passed (one model, one voice, ASR 0.84-0.97), but measured afterwards the 12 per-line takes ranged 112-174 Hz in median pitch. The film is now voiced in one TTS call and split back into lines by a small dynamic program, with per-line levelling: pitch 96-135 Hz, following the story (E16, F13).
- **My sister:** on Friday he held two radios, one at each ear, and the slip showed only a shoe. s10 now has one 1980s radio in his left hand, and s04 shows the whole man falling, drawn from the young uncle's face reference so it matches the other shots (3 candidates each; one retry drew a mobile phone).
- **Both cousins said they had never known this story about our uncle**, which is why the film exists.

The biggest lesson: viewers judge identity and continuity (his face, his year, his own words, one narrator's voice) before craft, and they read pictures literally. A boot was a symbol to me and a shoe to them. My automatic checks measured what I knew how to measure; three people watching the whole film found what they missed.

## 3. The hardest problem and how I solved it
**Amharic narration under a free quota.** Gemini TTS read my English style instruction aloud on 8 of 11 lines, but not
on the others, so nothing crashed and the film quietly got worse (FAILURES F7). I found it because takes were 17-19 s
regardless of length; an ASR round trip confirmed it. The documented short form ("Say warmly: …") still leaked. I built
two detectors (a duration guard and ASR similarity to the script, clean takes 0.84-0.97 and spoken prompts 0.37-0.48)
and finally removed in-text instructions altogether (EXPERIMENTS E5). Debugging this burned the daily quota of three TTS
models (F8): the quota is per model, per day. That led to a model fallback chain, and then to a new bug: the chain
voiced one line with a different model (F12). The fix was to pin the model and warn when takes come from more than one.
The general lesson: fallbacks protect availability but can quietly cost consistency, and a voice needs consistency.

## 4. A suggested practice that beat my instinct, and one that did not
**Beat my instinct: the reference sheet before keyframes.** I would have relied on a repeated text description. The
sheet, passed to FLUX.2 klein as a reference image, held his face across shots and let me draw the older uncle from the
younger one. It needed three iterations the brief doesn't mention: whole sheets leaked their layout (three copies of
him), full-body crops leaked the pose, and head-and-shoulders crops finally carried identity alone (E11-E13, each a
measured regeneration in runs.jsonl).

**Did not hold up: "a short style instruction improves a voice more than switching voices", and "a fixed seed makes
experiments comparable".** For Gemini TTS in Amharic, the style instruction was spoken aloud (E5); switching voices
was what worked (E14). On hosted FLUX, the same seed and prompt gave different images (E2: two md5s), so my
reproducibility comes from the content-addressed cache, not from seeds.

## 5. Ceiling work
- **An original score composed in code** in Ethiopian qenet modes (tizita, ambassel, bati major) with a leitmotif and a silence cue, deterministic and GPU-free; seed chosen by measured voice-band masking (E9), ducking release by measured pumping (E10).
- **Self-listening QA:** ASR round trip per narration line (E7).
- **A blind three-voice benchmark** (Gemini Charon vs Addis AI vs Microsoft Ameha), loudness-matched to -20 LUFS (E15). Results: [FILL IN after ≥ 5 listeners].
- **A tool for others:** an MCP server (`plan`, `explain_shot`, `edit_shot` validated before writing, `render`) and `make plan`, which predicts regeneration without calling a model.
- **Provenance as a product:** the ship's-log page, generated from the run's own evidence.

## 6. What I would build next
Wan 2.2 clips for the three shots flagged `use_video` (the pier, the smoke, the Friday radio) on Kaggle; a small web form
where a relative who doesn't code tells a story in Amharic and gets a storyboard back; and a LoRA on the character sheet
to compare consistency against reference conditioning.

## Evidence index
`runs.jsonl` (every call) · `COSTS.md` (measured; $0.00 spent) · `EXPERIMENTS.md` (16) · `FAILURES.md` (13) ·
`DESIGN.md` · `ETHICS.md` (consent recorded 26 Nov 2026) · `tests/` (21 offline tests). Built with a coding agent
(Claude Code) under my direction: I designed the stages, the story and the experiments, and reviewed every change.
