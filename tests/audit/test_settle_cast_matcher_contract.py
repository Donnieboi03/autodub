"""Settle G2 — cast_matcher methods and unlabeled → jp_embed when refs exist."""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

from autodub.cast_match import resolve_cast_match
from autodub.cast_sheet import load_cast_sheet

CAST_METHODS = frozenset({"caption", "jp_embed", "default"})


def _write_tone_wav(path: Path, *, freq_hz: float, duration_s: float = 0.35, sr: int = 16000) -> None:
    n = max(1, int(sr * duration_s))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq_hz * i / sr)))
            for i in range(n)
        )
        w.writeframes(frames)


def _write_cast(path: Path, *, ref_wav: str | None) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "show": {"title": "Cast Matcher Holdout", "season": 1},
                "bindings": [
                    {
                        "character_id": "char_hero",
                        "name": "Hero",
                        "voice": {
                            "backend": "elevenlabs",
                            "voice_id": "voice_hero",
                            "ref_wav": ref_wav,
                        },
                    },
                    {
                        "character_id": "char_sidekick",
                        "name": "Sidekick",
                        "voice": {
                            "backend": "elevenlabs",
                            "voice_id": "voice_sidekick",
                            "ref_wav": None,
                        },
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_labeled_caption_wins_method_caption(tmp_path: Path):
    """Explicit Name: label → method caption; never overridden by JP similarity."""
    _write_cast(tmp_path / "cast.json", ref_wav=None)
    sheet = load_cast_sheet(tmp_path / "cast.json")
    result = resolve_cast_match("Hero: We leave at dawn.", sheet)
    assert result.method == "caption"
    assert result.method in CAST_METHODS
    assert result.binding is not None
    assert result.binding.character_id == "char_hero"


def test_unlabeled_without_refs_uses_default_not_caption(tmp_path: Path):
    """No Name: prefix and no cast refs → default (not a false caption parse)."""
    _write_cast(tmp_path / "cast.json", ref_wav=None)
    sheet = load_cast_sheet(tmp_path / "cast.json")
    result = resolve_cast_match("We leave at dawn.", sheet, vocals_slice=None)
    assert result.method in CAST_METHODS
    assert result.method != "caption"
    assert result.method == "default"


def test_unlabeled_with_matching_refs_uses_jp_embed(tmp_path: Path):
    """Unlabeled cue + cast ref_wav bank + vocals slice → jp_embed when matchable."""
    ref = tmp_path / "hero_ref.wav"
    slice_wav = tmp_path / "line_vocals.wav"
    # Matching tones → high spectral/embed similarity above threshold (0.25)
    _write_tone_wav(ref, freq_hz=220.0)
    _write_tone_wav(slice_wav, freq_hz=220.0)
    _write_cast(tmp_path / "cast.json", ref_wav="hero_ref.wav")
    sheet = load_cast_sheet(tmp_path / "cast.json")

    result = resolve_cast_match(
        "We leave at dawn.",
        sheet,
        vocals_slice=slice_wav,
    )
    assert result.method in CAST_METHODS
    assert result.method == "jp_embed", (
        f"expected jp_embed when unlabeled + refs exist, got {result.method!r} "
        f"confidence={result.confidence!r}"
    )
    assert result.binding is not None
    assert result.binding.character_id == "char_hero"


def test_labeled_not_overridden_by_jp_embed_even_with_refs(tmp_path: Path):
    """Caption label always wins over JP similarity (CONTRACT dual-source rule)."""
    ref = tmp_path / "hero_ref.wav"
    slice_wav = tmp_path / "line_vocals.wav"
    _write_tone_wav(ref, freq_hz=220.0)
    _write_tone_wav(slice_wav, freq_hz=440.0)  # different tone; still must not override label
    _write_cast(tmp_path / "cast.json", ref_wav="hero_ref.wav")
    sheet = load_cast_sheet(tmp_path / "cast.json")

    result = resolve_cast_match(
        "Sidekick: Wait for me!",
        sheet,
        vocals_slice=slice_wav,
    )
    assert result.method == "caption"
    assert result.binding is not None
    assert result.binding.character_id == "char_sidekick"
