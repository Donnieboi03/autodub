# AutoDub behaviour contract (v1 / Milestone 0.6 + settle)

## Inputs

- Episode media file (local) with JP (or mixed) audio
- EN captions as a **user-supplied sidecar** (`.ass` / `.srt` / `.vtt`) when present
- Cast sheet binding character → voice backend id / ref (**house/stock voices** in public examples)

## Outputs

- File mode: external `.mka` EN dialogue stem + mix metadata JSON
- **Watch mode:** `autodub watch` runs the file pipeline if needed, then plays video + EN track (ffplay/mpv)
- **Episode report:** `*.autodub.report.json` with stage timings, cost estimate, fit stats, `me_method`, cast/scorecard fields (below)
- **Scorecard:** `*.autodub.scorecard.md` next to the report — ADHD gate table for agents/operators
- **Events sink:** `out/events.jsonl` (one JSON object per event line) for agent grepping
- **Voice score (optional CLI):** `autodub score-voice --ref REF.wav --hyp HYP.wav` → cosine speaker similarity
- **Score-run CLI:** `autodub score-run --out DIR` aggregates `spk_sim` + `cast_method` from a finished run
- Overlay mode (post-M0): on-point EN synced to `video.currentTime`, with vocal suppress/duck when audio tap works

## Dual-source rule (locked)

AutoDub does **not** invent script from JP audio alone. Speaker identity uses captions when labeled; otherwise **cast_matcher** may map JP vocals → cast.

| Source | Owns |
| :--- | :--- |
| **EN caption sidecar** | Spoken **words** (script fidelity). **Speaker identity** when a machine-readable label exists (`Name:` prefix and/or ASS style name → `character_id`) — labels always win |
| **JP / source vocals stem** (Demucs `vocals` when available) | **Tone / expression** → `PerformanceCue` (bucket, arousal, F0, rate, EL stability/style). When captions lack a speaker label: **cast_matcher** cosine-matches the line vocals slice against cast `ref_wav` banks → `character_id` (else `unknown`/`narrator`) |

**cast_matcher:** method ∈ `{caption, jp_embed, default}`. `jp_embed` accepts the best cast ref above threshold (default **0.25**, calibrate later). Explicit `Luffy:` (etc.) is never overridden by JP similarity. Soft SIM / `spk_sim` never replaces caption-verify for IVC enrollment.

Verify-by-caption is a **system rule**, not ear-vibes: IVC enrollment and cast identity *claims* must be checkable against labeled captions covering the enrollment window.

## Settle gates (definition of OK)

| ID | Gate | Pass |
| :--- | :--- | :--- |
| G1 | Ear | Operator would show a friend the demo watch |
| G2 | Cast | Caption wins; unlabeled → `jp_embed` when refs exist; report `cast_method` |
| G3 | SIM | Mean EN-ref→role hyp **≥ ~0.45** *and* G1 (SIM alone never ships) |
| G4 | Timing | `fit_ok_ratio` ≥ 0.9 on demo |
| G5 | Bed | demucs + audible duck under dialogue (`duck_gain` reported) |
| G6 | Emotion | PerformanceCue buckets drive distinct EL controls |
| G7 | Cost truth | ≥5 min (or dense multi-scene) run logged in `operator/COST.md` |
| G8 | Hygiene | `uv run --extra dev pytest` green; cache hits on identical re-run |
| G9 | Ethics | No IVC/refs in public git or public posts |

## Rules

1. **Caption fidelity:** when EN captions exist, spoken text equals caption text (whitespace-normalized). No MT invention in that mode.
2. **Cast lock:** after lock, same `character_id` → same voice for the episode/season.
3. **Guests/unknowns / unlabeled cues:** when EN captions omit speaker labels, prefer **cast_matcher** (JP vocal embed → cast ref bank → EN voice) before parking on house voice. Low-confidence or failed match → `unknown`/`narrator` house voice (or zero-shot from slice when enabled); never assign a wrong main-cast voice below confidence threshold. Missing `voice_id` falls back to stock and sets `voice_fallback=stock` (do not fail silently).
4. **Timing fit:** each EN chunk targets the caption speech window (`end_s - start_s`).
   - After TTS, stretch duration into **0.85–1.15×** of target when needed (WSOLA/rubberband/ffmpeg).
   - `fit_ok` is true when final duration is within that band (or shorter and padded by silence into the window).
   - Optional `--allow-caption-trim`: shorten caption text for timing only; manifest must set `text_source=caption_trimmed`. Default: no trim.
   - Performance cues record `target_s` for logging / rate hints; duration lock remains post-TTS fit in Phase 1.
5. **Performance (Phase 1):** per-line delivery from the **Demucs vocals stem** when available (not the full mix), plus caption punctuation (`!`, `...`, caps).
   - Emit a **PerformanceCue** with at least: `bucket` ∈ `{whisper, calm, neutral, intense, shout}`, `arousal`, `f0_mean`, `f0_range`, `speech_rate`, `target_s`, and EL controls (`stability`, `style`, `similarity_boost`).
   - Map cue → ElevenLabs voice settings. Shout/intense → lower stability + higher style than calm/whisper.
   - Manifest line includes `emotion` (bucket alias) and `performance` object.
   - If vocals stem is missing (non-demucs M&E), fall back to mix-slice analysis and set `performance.source=mix_fallback`.
   - Non-verbal JP (laugh/gasp without script) may passthrough.
6. **Loudness (file):** dialogue target about −24 LUFS ±2 (listenable M0; exact LUFS may be approximate).
7. **M&E:** prefer Demucs (or configured separator) `no_vocals` bed; when Demucs runs, keep **vocals** available for performance analysis; fallback stereotools must be reported as `me_method`. Report `demucs_cache_hit` (bool) and `duck_gain`.
8. **Speaker similarity (soft gate):** `score-voice` compares two wavs via speaker embedding cosine (ECAPA). Soft QA only — not sole acceptance. When scored into a run, report **must** include `spk_sim` when a cast `ref_wav` or `--score-ref` is available. Soft SIM never overrides caption-verify for IVC enrollment.
9. **Overlay readiness (post-M0):** when cues are prefetchable, chunk exists before cue start; start within ~150 ms after nudge.
10. **IVC / ref enrollment policy:**
    - Instant Voice Clone from third-party dub refs is **operator/personal only**. Public repo must not ship celebrity clone IDs or reference audio.
    - Enrollment media **must** ship a speaker-labeled caption sidecar (or ASS style name) covering the slice `[start_s, end_s]`.
    - `autodub voices ivc` **requires** `--subs` and a character identity (`--character`, or `--name` mapped to `character_id`). It loads captions and asserts the window overlaps cue(s) whose speaker prefix/style matches that character (case-insensitive). No matching labeled cue → fail fast with `caption-verify failed`.
    - Optional `--force-unverified` is an operator escape only; it must emit a warning event and must not be treated as caption-verified.
    - **Human reject path:** operator may mark a ref bank / enrollment **REJECTED** (operator README / DECISIONS). Cast must not claim that `character_id` via the rejected IVC until new **caption-aligned** EN refs pass verify. Prefer stock/house voice for that role meanwhile.

## Failure behaviour

- Missing captions (file): fail fast with clear error (MT path is explicit opt-in later).
- `voices ivc` without `--subs`, or caption-verify mismatch / unlabeled window: fail fast (`caption-verify failed`) unless `--force-unverified`.
- `audio_tap_unavailable`: play EN over full mix and surface a warning; do not crash.
- `overlay_underrun`: log event; skip or late-play per policy (document in DECISIONS locally).
- `watch` without media/subs/cast: fail fast (non-zero exit).
- `score-voice` without `--ref`/`--hyp` files: fail fast (non-zero exit). If the embedding backend is not installed, exit non-zero with a clear install hint (do not crash traceback-only).
- `score-run` without a finished report under `--out`: fail fast (non-zero exit).

## Required events

`line_rendered`, `cast_matched` (payload includes `method` + `confidence`), `cache_hit`, `overlay_underrun`, `audio_tap_unavailable`, `me_stem_ready`, `performance_resolved`, `voice_fallback` (when stock fallback used)

Events are printed to stderr **and** appended to `out/events.jsonl` when a run `out_dir` is active.

## Episode report schema (required keys)

`media`, `subs`, `cast`, `mka`, `model`, `me_method`, `stages_ms` (object with extract/demucs_or_me/tts/fit/mix/encode), `chars_sent`, `cache_hits`, `lines`, `fit_ok_ratio`, `est_credits`, `cast_method_histogram` (object: method → count), `duck_gain` (number), `demucs_cache_hit` (bool)

Optional / when available: `spk_sim` (number), `voice_fallback` (`stock`).

Line manifests must carry per-line: `cast_method`, `cast_confidence`, `performance`, and `cache_hit`.

## Scorecard schema (required)

File: `{stem}.autodub.scorecard.md` beside the report. Must include:

- Model, `me_method`, `duck_gain`, `fit_ok_ratio`, `cache_hits`, `est_credits`, `spk_sim` (or `n/a`)
- `cast_method` histogram
- Gate stubs G1–G9 with status placeholders (`pending` / metrics filled where automatic)

## Cache key stability

TTS render cache key must be stable for identical `(voice_id, script, performance_bucket, model)`. Demucs stem cache must key on media content hash so identical re-runs set `demucs_cache_hit=true`.
