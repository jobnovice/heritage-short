# Design

Written before any image or clip was generated (the storyboard commit `d8772d9` predates every keyframe).

## Audience
- **Primary:** my family: cousins and siblings in Addis Ababa and abroad who have heard pieces of my uncle's story at gatherings but never the whole of it, and the uncle himself.
- **Secondary:** Amharic-speaking followers on TikTok and Telegram.
- **Persona:** *Hana, 24, a cousin in Addis.* She watches on her phone, vertical, often with the sound low on a minibus, after the clip is forwarded in a family Telegram group. She reads Amharic, likes English subtitles for sharing with friends, and gives a clip about 3 seconds before scrolling.

## Viewing context
Phone, vertical (9:16), probably first watched without full attention. Consequences: the title and the first line must hook within 3 s; burned-in subtitles above the platform UI (bottom 22% kept clear); subjects composed at the centre so 9:16 and 16:9 crop from one master; no information that depends on reading small text.

## Intent
When it ends the viewer should **feel how close he came** (two days, one slip), feel **gratitude rather than triumph**, **understand** why he now says "ሕይወትህን እግዚአብሔር ይምራው" (let God lead your life), and **remember the comrades who did not come back**.

How might we… help my cousins feel the weight of a single Tuesday that decided my uncle's life?

## Ideation (approaches considered)
1. **Chronological testimony:** navy life → injury → news → faith. Clear but flat, and the twist is announced too early.
2. **Start at the sinking, then flash back:** dramatic, but it leads with violence and turns a family story into a war film.
3. **Days of the week (chosen):** Tuesday (the fall), Wednesday (despair), Thursday (the ship sails), then Today. The title "ሐሙስ / Thursday" is a promise the audience understands only at s08. It keeps the war at a distance (smoke on a horizon, silence) and puts the turn on one small, human moment.

## Story and structure
- **Logline:** a young Derg-era sailor breaks his arm two days before his ship sails for Massawa; the ship never returns, and the fall he cursed becomes the reason he preaches.
- **Motifs:** the sling (s05 → s06 → s08 → the forearm on the Bible in s10); the sea (s01 → the window in s11).
- **Music:** Ethiopian qenet as narrative. Tizita (the mode of longing) for memory, ambassel for the fall, **a silence cue for the loss**, and the Massawa theme returning in bati major for grace. Cue reasons are in `storyboard.json → music.cues[].purpose`.
- **Every shot has a stated reason:** `storyboard.json → shots[].reason` (validated as required by the schema).

## Sensitive choices
- **His despair:** he told me he considered suicide. The film says "he lost all hope; it felt like the end of the world" and shows nothing explicit. [FILL IN: confirm with uncle that he is comfortable with this wording.]
- **The war:** narration says the ship "never came back" and the men "stayed with the sea". It names no enemy, so Eritrean viewers are not cast as villains in a story about loss on all sides.
- **Historical facts:** I state no date or vessel name. [FILL IN: date / ship name if the uncle confirms; reference: fall of Massawa, Feb 1990.]

---

## User test 1: radio cut (narration + placeholder score on black)
File: `outputs/final/radio_cut_9x16.mp4` (74.8 s, Addis AI voice). At least 3 people from the audience.

Questions asked: (1) What did you feel at the end? (2) Where did your attention drop? (3) Any Amharic that sounded wrong or unnatural? (4) What do you think "ሐሙስ" refers to before it is explained?

| # | Who (relation, age, where) | How (in person / Telegram) | What they said (verbatim where possible) |
|---|---|---|---|
| 1 | [FILL IN] | [FILL IN] | [FILL IN] |
| 2 | [FILL IN] | [FILL IN] | [FILL IN] |
| 3 | [FILL IN] | [FILL IN] | [FILL IN] |

**Insights:** [FILL IN]
**Changes made to storyboard.json because of test 1** (with commit hashes): [FILL IN]

## Review round 1: first full cut (26 Nov, ~02:30 EAT)
Feedback relayed to me by the filmmaker from family reviewers. [FILL IN: who (relation), how they watched.]

| Feedback | Change in storyboard.json | Commit |
|---|---|---|
| The older uncle (preaching) does not look like the young uncle: his skin is lighter | Both descriptions fix "dark brown skin"; `uncle_now` sheet is now generated *from* `uncle_young`'s face reference (`reference_from`) | `feat(storyboard): review round 1` + keyframe regen |
| "A random Tuesday and Thursday": no year | s01 now says 1982 E.C. (1989/90) | same |
| Missing his own turning point: Friday, when he heard the news, is the day he calls his rebirth | New shot s10 "Friday" (radio at the base, sling, first light); old s10/s11 become s11/s12 | same |
| The film should say why the ship sank | s09 states it was sunk in an attack by Eritrean fighters that same Thursday (I had first left the cause out to stay neutral; the family's telling names it, and it is their story) | same |
| The narrator should be a man | Gemini `Charon` (median F0 ≈ 150 Hz) replaces the Addis AI default voice (≈ 220 Hz); EXPERIMENTS E14 | `feat(narration): male narrator` |

## User test 2: near-final cut
File: `outputs/final/thursday_9x16.mp4`. At least 3 people (they may overlap with test 1).

| # | Who | How | What they said |
|---|---|---|---|
| 1 | [FILL IN] | [FILL IN] | [FILL IN] |
| 2 | [FILL IN] | [FILL IN] | [FILL IN] |
| 3 | [FILL IN] | [FILL IN] | [FILL IN] |

**Insights:** [FILL IN]
**Changes made because of test 2:** [FILL IN]
