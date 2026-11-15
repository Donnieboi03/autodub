"""Environment loading. Secrets never logged."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    """Load `.env` from repo root if present."""
    load_dotenv(_REPO_ROOT / ".env")


def elevenlabs_key_present() -> bool:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    return bool(key)


def elevenlabs_tts_model() -> str:
    """Resolve TTS model: AUTODUB_TTS_MODEL → ELEVENLABS_TTS_MODEL → Flash default."""
    for key in ("AUTODUB_TTS_MODEL", "ELEVENLABS_TTS_MODEL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return "eleven_flash_v2_5"
