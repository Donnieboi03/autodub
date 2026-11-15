"""Mood / emotion bucket from a JP (or any) dialogue slice."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def emotion_bucket_from_wav(path: Path | str) -> str:
    """
    Cheap energy/rate proxy → calm | neutral | intense.
    Used to bias ElevenLabs style; not a full emotion model.
    """
    path = Path(path)
    if not path.is_file():
        return "neutral"
    try:
        audio, sr = sf.read(str(path), always_2d=True)
    except Exception:
        return "neutral"
    mono = audio.mean(axis=1)
    if mono.size < sr * 0.05:
        return "neutral"
    rms = float(np.sqrt(np.mean(mono**2)) + 1e-9)
    # zero-crossing rate as rough excitation
    zc = float(np.mean(np.abs(np.diff(np.signbit(mono)))))
    if rms > 0.12 or zc > 0.15:
        return "intense"
    if rms < 0.03:
        return "calm"
    return "neutral"


def style_for_bucket(bucket: str) -> float:
    return {"calm": 0.15, "neutral": 0.35, "intense": 0.65}.get(bucket, 0.35)
