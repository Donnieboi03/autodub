"""Fixtures for promoted acceptance tests (synthetic only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def synthetic_srt(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic.en.srt"
    path.write_text(
        "1\n"
        "00:00:01,000 --> 00:00:03,000\n"
        "Hero: We leave at dawn.\n"
        "\n"
        "2\n"
        "00:00:03,500 --> 00:00:05,500\n"
        "  Sidekick:   Wait   for   me!  \n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def locked_cast_sheet(tmp_path: Path) -> Path:
    path = tmp_path / "locked.cast.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "show": {"title": "Audit Synthetic", "season": 1},
                "bindings": [
                    {
                        "character_id": "char_hero",
                        "name": "Hero",
                        "voice": {
                            "backend": "elevenlabs",
                            "voice_id": "audit_voice_hero_locked",
                        },
                    },
                    {
                        "character_id": "char_sidekick",
                        "name": "Sidekick",
                        "voice": {
                            "backend": "elevenlabs",
                            "voice_id": "audit_voice_sidekick_locked",
                        },
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
