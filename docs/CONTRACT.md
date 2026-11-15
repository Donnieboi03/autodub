# AutoDub behaviour contract (v1)

## Inputs

- Episode media file (local) **or** browser player with EN captions
- EN captions (`.ass` / `.srt` / `.vtt` / TextTrack cues) when present
- Cast sheet binding character → voice backend id / ref

## Outputs

- File mode: external `.mka` (or equivalent) EN dialogue stem + mix metadata JSON
- Overlay mode: on-point EN audio synced to `video.currentTime`, with vocal suppress/duck when audio tap works

## Rules

1. **Caption fidelity:** when EN captions exist, spoken text equals caption text (whitespace-normalized). No MT invention in that mode.
2. **Cast lock:** after lock, same `character_id` → same voice for the episode/season.
3. **Guests/unknowns:** zero-shot from that speaker’s audio slice → EN caption text.
4. **Timing:** EN chunk scheduled to caption/speech window; sync nudge supported.
5. **Loudness (file):** dialogue target about −24 LUFS ±2.
6. **Overlay readiness:** when cues are prefetchable, chunk exists before cue start; start within ~150 ms after nudge.

## Failure behaviour

- Missing captions (file): fail fast with clear error (MT path is explicit opt-in later).
- `audio_tap_unavailable`: play EN over full mix and surface a warning; do not crash.
- `overlay_underrun`: log event; skip or late-play per policy (document in DECISIONS locally).

## Required events

`line_rendered`, `cast_matched`, `cache_hit`, `overlay_underrun`, `audio_tap_unavailable`
