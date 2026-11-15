# AutoDub

Unofficial English dialogue track for anime you can already play: caption-faithful words, stable voices per character, pre-rendered chunks mixed or overlaid on-point.

**Bring your own keys and voices.** This repo does not ship voice models of real people or episode media.

## Quick start

```bash
cp .env.example .env
# edit .env → set ELEVENLABS_API_KEY

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# optional real vocal removal for M&E beds (falls back to ffmpeg stereotools):
#   PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 pip install -e ".[separate]"   # demucs
#   pip install 'audio-separator[cpu]'                                 # UVR/MelBand
autodub doctor
```

M&E cascade: **demucs → audio-separator → stereotools**. Override with `AUTODUB_ME_METHOD`. Model weights stay in local caches — never commit them.

Local-only (gitignored): `operator/` (cost, cast sheets, handoffs, media) and `holdout/` (blind acceptance — verifier only).

## File pipeline (synthetic smoke)

```bash
# bootstrap cast from your EL stock voices (writes operator/ — not committed)
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

`voices ivc` is **operator/personal only** (not for public cast sheets). It requires a real media path and fails fast if missing.

## Overlay

Load `extension/` unpacked in Chrome. Open `extension/fixture.html`, capability-probe, then point at a run manifest. See `extension/README.md`.

## Layout

- `src/autodub/` — engine + CLI
- `extension/` — MV3 overlay + HTML5 fixture
- `cast/examples/` — cast sheet schema only (no real voice IDs)
- `docs/CONTRACT.md` — behaviour contract
- `tests/` — implementer unit tests; `tests/audit/` for promoted acceptance

## Ethics

See [ETHICS.md](ETHICS.md).
