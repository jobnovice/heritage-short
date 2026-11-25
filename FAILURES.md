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
