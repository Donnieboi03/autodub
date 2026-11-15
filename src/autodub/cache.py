"""Render cache keyed by voice + text + emotion bucket."""

from __future__ import annotations

import hashlib
from pathlib import Path


def cache_key(voice_id: str, text: str, emotion_bucket: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(voice_id.encode())
    h.update(b"\0")
    h.update(text.encode())
    h.update(b"\0")
    h.update(emotion_bucket.encode())
    h.update(b"\0")
    h.update(model.encode())
    return h.hexdigest()[:24]


def cache_path(root: Path, key: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{key}.mp3"
