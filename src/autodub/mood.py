"""Mood / emotion from JP dialogue slice + caption punctuation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


@dataclass(frozen=True)
class EmotionSettings:
    bucket: str
    stability: float
    similarity_boost: float
    style: float


def emotion_bucket_from_wav(path: Path | str) -> str:
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
    zc = float(np.mean(np.abs(np.diff(np.signbit(mono)))))
    # crude F0 proxy: spectral centroid-ish via zero crossings already; boost intense
    if rms > 0.12 or zc > 0.15:
        return "intense"
    if rms < 0.03:
        return "calm"
    return "neutral"


def emotion_from_caption_text(text: str) -> str | None:
    t = text.strip()
    if not t:
        return None
    letters = [c for c in t if c.isalpha()]
    caps_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0.0
    if t.endswith("!!!") or caps_ratio > 0.7:
        return "intense"
    if "!" in t:
        return "intense"
    if t.endswith("...") or t.endswith("…"):
        return "calm"
    return None


def resolve_emotion(wav_path: Path | str, caption_text: str) -> EmotionSettings:
    audio_bucket = emotion_bucket_from_wav(wav_path)
    punct = emotion_from_caption_text(caption_text)
    # punctuation can escalate to intense; calm from dots only if audio not intense
    if punct == "intense" or audio_bucket == "intense":
        bucket = "intense"
    elif punct == "calm" and audio_bucket != "intense":
        bucket = "calm"
    else:
        bucket = audio_bucket
    return settings_for_bucket(bucket)


def settings_for_bucket(bucket: str) -> EmotionSettings:
    if bucket == "intense":
        return EmotionSettings("intense", stability=0.25, similarity_boost=0.8, style=0.75)
    if bucket == "calm":
        return EmotionSettings("calm", stability=0.55, similarity_boost=0.7, style=0.15)
    return EmotionSettings("neutral", stability=0.4, similarity_boost=0.75, style=0.35)


def style_for_bucket(bucket: str) -> float:
    return settings_for_bucket(bucket).style
