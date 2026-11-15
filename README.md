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
autodub doctor
```

Local-only (gitignored): `operator/` (cost, cast sheets, handoffs) and `holdout/` (blind acceptance — verifier only).

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

# play with external audio
mpv --audio-file=operator/runs/synthetic/synthetic.autodub.mka \
    operator/fixtures/synthetic/synthetic.mp4
```

`voices ivc` requires a real media path; it fails fast if missing (do not invent show media).

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
