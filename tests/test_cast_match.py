"""Cast matcher: caption wins; JP embed vs synthetic tone refs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from autodub.cast_match import JP_EMBED_THRESHOLD, resolve_cast_match
from autodub.cast_sheet import load_cast_sheet, write_cast_sheet
from autodub.score_voice import spectral_similarity


def _write_tone(path: Path, freq_hz: float, *, duration_s: float = 0.4, sr: int = 16000) -> Path:
    t = np.linspace(0.0, duration_s, int(sr * duration_s), endpoint=False)
    mono = (0.2 * np.sin(2.0 * np.pi * freq_hz * t)).astype(np.float32)
    sf.write(str(path), mono, sr)
    return path


def _cast_with_refs(tmp_path: Path, luffy_ref: Path, uta_ref: Path) -> Path:
    path = tmp_path / "cast.json"
    write_cast_sheet(
        path,
        {
            "schema_version": 1,
            "show": {"title": "T", "season": 1},
            "bindings": [
                {
                    "character_id": "narrator",
                    "name": "Narrator",
                    "voice": {"backend": "elevenlabs", "voice_id": "vid0"},
                },
                {
                    "character_id": "luffy",
                    "name": "Luffy",
                    "voice": {
                        "backend": "elevenlabs",
                        "voice_id": "vid1",
                        "ref_wav": str(luffy_ref),
                    },
                },
                {
                    "character_id": "uta",
                    "name": "Uta",
                    "voice": {
                        "backend": "elevenlabs",
                        "voice_id": "vidu",
                        "ref_wav": str(uta_ref),
                    },
                },
            ],
        },
    )
    return path


def test_caption_prefix_wins_over_jp_slice(tmp_path: Path):
    luffy = _write_tone(tmp_path / "luffy.wav", 220.0)
    uta = _write_tone(tmp_path / "uta.wav", 880.0)
    slice_uta = _write_tone(tmp_path / "slice.wav", 880.0)
    cast = load_cast_sheet(_cast_with_refs(tmp_path, luffy, uta))
    result = resolve_cast_match(
        "Luffy: I'm gonna be King!",
        cast,
        vocals_slice=slice_uta,
        similarity_fn=spectral_similarity,
    )
    assert result.method == "caption"
    assert result.binding.character_id == "luffy"
    assert result.script == "I'm gonna be King!"
    assert result.confidence == 1.0


def test_jp_embed_picks_matching_tone(tmp_path: Path):
    luffy = _write_tone(tmp_path / "luffy.wav", 220.0)
    uta = _write_tone(tmp_path / "uta.wav", 880.0)
    slice_uta = _write_tone(tmp_path / "slice.wav", 880.0)
    cast = load_cast_sheet(_cast_with_refs(tmp_path, luffy, uta))
    # Distinct tones: spectral cosine should prefer Uta
    assert spectral_similarity(uta, slice_uta) > spectral_similarity(luffy, slice_uta)
    result = resolve_cast_match(
        "No speaker prefix here",
        cast,
        vocals_slice=slice_uta,
        similarity_fn=spectral_similarity,
        threshold=0.5,
    )
    assert result.method == "jp_embed"
    assert result.binding.character_id == "uta"
    assert result.confidence >= 0.5


def test_jp_embed_below_threshold_defaults_narrator(tmp_path: Path):
    luffy = _write_tone(tmp_path / "luffy.wav", 220.0)
    uta = _write_tone(tmp_path / "uta.wav", 880.0)
    # 4 kHz is spectrally far from 220/880 (55 Hz aliases with 220 on band FP)
    other = _write_tone(tmp_path / "slice.wav", 4000.0)
    cast = load_cast_sheet(_cast_with_refs(tmp_path, luffy, uta))
    assert spectral_similarity(luffy, other) < 0.5
    assert spectral_similarity(uta, other) < 0.5
    result = resolve_cast_match(
        "Unlabeled line",
        cast,
        vocals_slice=other,
        similarity_fn=spectral_similarity,
        threshold=0.5,
    )
    assert result.method == "default"
    assert result.binding.character_id == "narrator"


def test_no_refs_defaults_without_slice_match(tmp_path: Path):
    path = tmp_path / "cast.json"
    write_cast_sheet(
        path,
        {
            "schema_version": 1,
            "show": {"title": "T", "season": 1},
            "bindings": [
                {
                    "character_id": "narrator",
                    "name": "Narrator",
                    "voice": {"backend": "elevenlabs", "voice_id": "vid0"},
                },
                {
                    "character_id": "luffy",
                    "name": "Luffy",
                    "voice": {"backend": "elevenlabs", "voice_id": "vid1"},
                },
            ],
        },
    )
    cast = load_cast_sheet(path)
    slice_path = _write_tone(tmp_path / "slice.wav", 440.0)
    result = resolve_cast_match("Unlabeled", cast, vocals_slice=slice_path)
    assert result.method == "default"
    assert result.binding.character_id == "narrator"


def test_threshold_constant_documented():
    assert JP_EMBED_THRESHOLD == 0.25
