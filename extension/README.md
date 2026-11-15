# AutoDub browser overlay (MV3)

Caption-faithful EN dialogue over HTML5 `<video>`:

1. Prefetch chunks from a run manifest (`lines[].audio` / `chunk`)
2. Play on TextTrack cue / caption window (sync nudge via popup)
3. Duck / center-suppress the page audio when `MediaElementSource` tap works
4. If tap fails → play EN over full mix and emit `audio_tap_unavailable`

## Load unpacked

1. Chrome → `chrome://extensions` → Developer mode → Load unpacked → this `extension/` folder
2. Allow file URL access on the extension card if testing `file://` fixtures
3. Open `extension/fixture.html` (or serve over `http://127.0.0.1`)
4. Point popup **Manifest URL** at a local `*.autodub.json` from `autodub run`
5. **Capability probe** then **Start**

## Fixture

`fixture.html` embeds demo EN cues and the same content script. Attach
`operator/.../synthetic.mp4` (from `autodub fixture`) for A/V timing smoke.

## Events

`overlay_underrun`, `audio_tap_unavailable` (plus page CustomEvent `autodub-event`).
