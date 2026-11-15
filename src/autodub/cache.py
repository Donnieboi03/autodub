"""Render cache keyed by voice + text + emotion bucket (+ media hash helpers)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def _normalize_cache_text(text: str) -> str:
    """Stable whitespace so tiny caption formatting diffs do not bust the cache."""
    return re.sub(r"\s+", " ", (text or "").strip())


def cache_key(voice_id: str, text: str, emotion_bucket: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(str(voice_id).encode())
    h.update(b"\0")
    h.update(_normalize_cache_text(text).encode())
    h.update(b"\0")
    h.update(str(emotion_bucket or "neutral").strip().lower().encode())
    h.update(b"\0")
    h.update(str(model).encode())
    return h.hexdigest()[:24]


def cache_path(root: Path, key: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{key}.mp3"


def media_content_hash(path: Path | str, *, chunk_size: int = 1 << 20) -> str:
    """SHA-256 of file contents (first 16 hex chars) for Demucs / stem cache keys."""
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:16]
