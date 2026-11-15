"""PerformanceCue from vocals (or mix fallback) + caption punctuation → EL controls."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from autodub.mood import emotion_from_caption_text

BUCKETS = ("whisper", "calm", "neutral", "intense", "shout")


@dataclass(frozen=True)
class PerformanceCue:
    bucket: str
    arousal: float
    f0_mean: float
    f0_range: float
    speech_rate: float
    target_s: float
    stability: float
    similarity_boost: float
    style: float
    source: str  # vocals | mix_fallback

    def to_dict(self) -> dict:
        return asdict(self)


def _load_mono(path: Path) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(str(path), always_2d=True)
    mono = audio.mean(axis=1).astype(np.float64)
    return mono, int(sr)


def _arousal(mono: np.ndarray) -> float:
    if mono.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(mono**2)) + 1e-12)
    # map typical dialogue RMS into ~0–1
    return float(np.clip(rms / 0.25, 0.0, 1.0))


def _f0_stats(mono: np.ndarray, sr: int) -> tuple[float, float]:
    """Crude pitch proxy via short-time autocorrelation peaks."""
    if mono.size < sr * 0.05:
        return 0.0, 0.0
    frame = max(int(sr * 0.04), 256)
    hop = max(frame // 2, 128)
    f0s: list[float] = []
    # search 80–400 Hz
    min_lag = max(int(sr / 400), 2)
    max_lag = min(int(sr / 80), frame - 1)
    if max_lag <= min_lag:
        return 0.0, 0.0
    for start in range(0, max(0, mono.size - frame), hop):
        chunk = mono[start : start + frame]
        if float(np.sqrt(np.mean(chunk**2))) < 0.01:
            continue
        chunk = chunk - chunk.mean()
        corr = np.correlate(chunk, chunk, mode="full")[frame - 1 :]
        seg = corr[min_lag:max_lag]
        if seg.size == 0:
            continue
        lag = int(np.argmax(seg)) + min_lag
        if corr[lag] <= 0:
            continue
        f0s.append(float(sr) / float(lag))
    if not f0s:
        return 0.0, 0.0
    arr = np.asarray(f0s, dtype=np.float64)
    return float(arr.mean()), float(arr.max() - arr.min())


def bucket_from_features(
    arousal: float,
    f0_range: float,
    punct: str | None,
) -> str:
    """
    Bucket from arousal first; F0 range only boosts when energy is already up.
    (Crude F0 proxies are noisy on music beds and must not alone force shout.)
    """
    energetic = arousal >= 0.55 or (arousal >= 0.35 and f0_range >= 80)
    very_hot = arousal >= 0.85 or (arousal >= 0.6 and f0_range >= 120)
    if punct == "intense" or energetic:
        if very_hot or (punct == "intense" and arousal >= 0.45):
            return "shout" if very_hot else "intense"
        return "intense"
    if punct == "calm" or arousal <= 0.12:
        if arousal <= 0.06:
            return "whisper"
        return "calm"
    return "neutral"


def el_controls_for_bucket(bucket: str) -> tuple[float, float, float]:
    """Return stability, similarity_boost, style."""
    table = {
        "whisper": (0.65, 0.7, 0.1),
        "calm": (0.55, 0.7, 0.15),
        "neutral": (0.4, 0.75, 0.35),
        "intense": (0.25, 0.8, 0.75),
        "shout": (0.18, 0.85, 0.9),
    }
    return table.get(bucket, table["neutral"])


def analyze_wav_features(path: Path | str) -> tuple[float, float, float]:
    path = Path(path)
    if not path.is_file():
        return 0.0, 0.0, 0.0
    try:
        mono, sr = _load_mono(path)
    except Exception:
        return 0.0, 0.0, 0.0
    arousal = _arousal(mono)
    f0_mean, f0_range = _f0_stats(mono, sr)
    return arousal, f0_mean, f0_range


def resolve_performance(
    wav_path: Path | str,
    caption_text: str,
    *,
    target_s: float,
    source: str = "vocals",
) -> PerformanceCue:
    arousal, f0_mean, f0_range = analyze_wav_features(wav_path)
    punct = emotion_from_caption_text(caption_text)
    # map legacy mood punct labels: intense/calm only
    bucket = bucket_from_features(arousal, f0_range, punct)
    stability, similarity_boost, style = el_controls_for_bucket(bucket)
    speech_rate = (len(caption_text.strip()) / target_s) if target_s > 0 else 0.0
    return PerformanceCue(
        bucket=bucket,
        arousal=round(arousal, 4),
        f0_mean=round(f0_mean, 2),
        f0_range=round(f0_range, 2),
        speech_rate=round(speech_rate, 2),
        target_s=round(float(target_s), 4),
        stability=stability,
        similarity_boost=similarity_boost,
        style=style,
        source=source if source in {"vocals", "mix_fallback"} else "mix_fallback",
    )
