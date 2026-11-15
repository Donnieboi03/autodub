# AutoDub

Unofficial English dialogue track for anime you can already play: caption-faithful words, stable voices per character, pre-rendered chunks mixed or overlaid on-point.

**Dual-source (locked):** EN captions own **words**; speaker labels win when present. When captions lack a speaker, **cast_matcher** matches the JP/source vocals slice to cast `ref_wav` banks (else `unknown`/`narrator`). JP vocals also drive **PerformanceCue** (tone). IVC enrollment must pass caption-verify (`voices ivc --subs …`) — see `docs/CONTRACT.md`.

**Bring your own keys and voices.** This repo does not ship voice models of real people or episode media.

## Ethics

See [ETHICS.md](ETHICS.md). Do not redistribute episode/audio masters; do not claim official dubs; public examples use house/stock voices only; no DRM circumvention.

## Install

```bash
cp .env.example .env
# edit .env → set ELEVENLABS_API_KEY

# uv (preferred — lockfile committed)
uv sync --extra dev
uv run --extra dev pytest

# or pip
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest

# optional real vocal removal for M&E beds (falls back to ffmpeg stereotools):
#   PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 uv sync --extra separate   # demucs
#   uv sync --extra separate-uvr                                    # UVR/MelBand
# soft speaker SIM / cast_matcher ECAPA:
#   uv sync --extra score
autodub doctor
```

M&E cascade: **demucs → audio-separator → stereotools** (Demucs stems cached under `out/work` by media hash). Override with `AUTODUB_ME_METHOD`. Model weights stay in local caches — never commit them.

Local-only (gitignored): `operator/` (cost, cast sheets, handoffs, media) and `holdout/` (blind acceptance — verifier only).

## Synthetic demo (one-liner)

```bash
autodub fixture --out /tmp/ad-fix && \
autodub voices stock-cast --out /tmp/ad-cast.json && \
autodub run --media /tmp/ad-fix/synthetic.mp4 --subs /tmp/ad-fix/synthetic.en.srt \
  --cast /tmp/ad-cast.json --out /tmp/ad-run --limit-lines 2
```

Or the longer operator path:

```bash
autodub voices stock-cast --out operator/cast/bootstrap.cast.json
autodub fixture --out operator/fixtures/synthetic
autodub run \
  --media operator/fixtures/synthetic/synthetic.mp4 \
  --subs  operator/fixtures/synthetic/synthetic.en.srt \
  --cast  operator/cast/bootstrap.cast.json \
  --out   operator/runs/synthetic \
  --limit-lines 2

# one-shot: pipeline (if needed) + play
autodub watch \
  --media operator/fixtures/synthetic/synthetic.mp4 \
  --subs  operator/fixtures/synthetic/synthetic.en.srt \
  --cast  operator/cast/bootstrap.cast.json \
  --out   operator/runs/synthetic \
  --limit-lines 2
```

`voices ivc` is **operator/personal only** (not for public cast sheets). It requires `--media`, `--subs` (speaker-labeled captions covering the slice), and `--character` (or `--name` mapped to `character_id`). Caption-verify fails fast unless `--force-unverified`.

Optional soft SIM on a run: `--score-ref REF.wav` → report `spk_sim`.

## Overlay

Load `extension/` unpacked in Chrome. Open `extension/fixture.html`, capability-probe, then point at a run manifest. See `extension/README.md`.

## Layout

- `src/autodub/` — engine + CLI (`cast_match.py` = unlabeled-line identity)
- `extension/` — MV3 overlay + HTML5 fixture
- `cast/examples/` — cast sheet schema only (no real voice IDs)
- `docs/CONTRACT.md` — behaviour contract
- `tests/` — implementer unit tests; `tests/audit/` for promoted acceptance
