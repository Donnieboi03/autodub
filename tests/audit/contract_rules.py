"""Promoted from holdout — pure CONTRACT predicates."""

from __future__ import annotations

import re
from collections.abc import Mapping


def whitespace_normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def caption_fidelity_holds(caption_text: str, spoken_or_script_text: str, *, normalize) -> bool:
    return normalize(caption_text) == normalize(spoken_or_script_text)


def cast_lock_stable(character_id: str, voice_by_character: Mapping[str, str | None]) -> str:
    if character_id not in voice_by_character:
        raise KeyError(f"character_id not locked: {character_id}")
    voice_id = voice_by_character[character_id]
    if not voice_id:
        raise ValueError(f"locked character has empty voice_id: {character_id}")
    return voice_id


REQUIRED_EVENTS = frozenset(
    {
        "line_rendered",
        "cast_matched",
        "cache_hit",
        "overlay_underrun",
        "audio_tap_unavailable",
    }
)
