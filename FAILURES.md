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
