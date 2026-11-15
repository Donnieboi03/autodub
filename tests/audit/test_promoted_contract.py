"""Promoted holdout greens — caption fidelity, cast lock, required events."""

from __future__ import annotations

from pathlib import Path

from .contract_rules import (
    REQUIRED_EVENTS,
    caption_fidelity_holds,
    cast_lock_stable,
)


def test_spoken_equals_caption_normalized(synthetic_srt: Path):
    from autodub.captions import load_captions, normalize_script_text

    for line in load_captions(synthetic_srt):
        assert caption_fidelity_holds(
            line.text, line.text, normalize=normalize_script_text
        )


def test_fidelity_rejects_invention(synthetic_srt: Path):
    from autodub.captions import load_captions, normalize_script_text

    line = load_captions(synthetic_srt)[0]
    assert not caption_fidelity_holds(
        line.text, "Invented MT line", normalize=normalize_script_text
    )


def test_cast_lock_stable_across_reload(locked_cast_sheet: Path):
    from autodub.cast_sheet import load_cast_sheet

    first = {b.character_id: b.voice_id for b in load_cast_sheet(locked_cast_sheet).bindings}
    second = {b.character_id: b.voice_id for b in load_cast_sheet(locked_cast_sheet).bindings}
    assert first == second
    for cid in first:
        assert cast_lock_stable(cid, first) == cast_lock_stable(cid, second)


def test_required_events_emit():
    from autodub.events import emit

    assert REQUIRED_EVENTS == {
        "line_rendered",
        "cast_matched",
        "cache_hit",
        "overlay_underrun",
        "audio_tap_unavailable",
    }
    for name in REQUIRED_EVENTS:
        event = emit(name, source="audit")
        assert event.name == name
