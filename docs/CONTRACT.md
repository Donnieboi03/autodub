# AutoDub behaviour contract (v1 / Milestone 0)

## Inputs

- Episode media file (local) with JP (or mixed) audio
- EN captions as a **user-supplied sidecar** (`.ass` / `.srt` / `.vtt`) when present
- Cast sheet binding character → voice backend id / ref (**house/stock voices** in public examples)

## Outputs

- File mode: external `.mka` EN dialogue stem + mix metadata JSON
- **Watch mode:** `autodub watch` runs the file pipeline if needed, then plays video + EN track (ffplay/mpv)
- **Episode report:** `*.autodub.report.json` with stage timings, cost estimate, fit stats, `me_method`
- Overlay mode (post-M0): on-point EN synced to `video.currentTime`, with vocal suppress/duck when audio tap works

## Rules

1. **Caption fidelity:** when EN captions exist, spoken text equals caption text (whitespace-normalized). No MT invention in that mode.
2. **Cast lock:** after lock, same `character_id` → same voice for the episode/season.
3. **Guests/unknowns:** low-confidence or unknown speaker → `unknown`/`narrator` house voice (or zero-shot from slice when enabled); never assign a wrong main-cast voice below confidence threshold.
4. **Timing fit:** each EN chunk targets the caption speech window (`end_s - start_s`).
   - After TTS, stretch duration into **0.85–1.15×** of target when needed (WSOLA/rubberband/ffmpeg).
   - `fit_ok` is true when final duration is within that band (or shorter and padded by silence into the window).
   - Optional `--allow-caption-trim`: shorten caption text for timing only; manifest must set `text_source=caption_trimmed`. Default: no trim.
5. **Emotion:** per-line emotion from JP audio slice (loudness / excitation) plus caption punctuation (`!`, `...`, caps); passed into TTS voice settings. Non-verbal JP (laugh/gasp without script) may passthrough.
6. **Loudness (file):** dialogue target about −24 LUFS ±2 (listenable M0; exact LUFS may be approximate).
7. **M&E:** prefer Demucs (or configured separator) `no_vocals` bed; fallback stereotools must be reported as `me_method`.
8. **Overlay readiness (post-M0):** when cues are prefetchable, chunk exists before cue start; start within ~150 ms after nudge.
9. **IVC policy:** Instant Voice Clone from third-party dub refs is **operator/personal only**. Public repo must not ship celebrity clone IDs or reference audio.

## Failure behaviour

- Missing captions (file): fail fast with clear error (MT path is explicit opt-in later).
- `audio_tap_unavailable`: play EN over full mix and surface a warning; do not crash.
- `overlay_underrun`: log event; skip or late-play per policy (document in DECISIONS locally).
- `watch` without media/subs/cast: fail fast (non-zero exit).

## Required events

`line_rendered`, `cast_matched`, `cache_hit`, `overlay_underrun`, `audio_tap_unavailable`, `me_stem_ready`

## Episode report schema (required keys)

`media`, `subs`, `cast`, `mka`, `model`, `me_method`, `stages_ms` (object with extract/demucs_or_me/tts/fit/mix/encode), `chars_sent`, `cache_hits`, `lines`, `fit_ok_ratio`, `est_credits`
