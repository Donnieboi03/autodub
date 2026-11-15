# AutoDub

Unofficial English dialogue track for anime you can already play: caption-faithful words, stable voices per character, pre-rendered chunks mixed or overlaid on-point.

**Bring your own keys and voices.** This repo does not ship voice models of real people or episode media.

## Quick start (keys)

```bash
cp .env.example .env
# edit .env → set ELEVENLABS_API_KEY
```

Local-only operator notes (cost log, real cast sheets, agent handoffs) live in `operator/` — gitignored.

## Status

Scaffold. Pipeline and overlay land next.

## Layout

- `src/autodub/` — engine
- `extension/` — browser overlay (soon)
- `cast/examples/` — cast sheet schema only
- `docs/CONTRACT.md` — behaviour contract
- `docs/HANDOFF.template.md` — copy into `operator/handoffs/` for agents
- `tests/` / `holdout/` — unit vs blind acceptance

## Ethics

See [ETHICS.md](ETHICS.md).
