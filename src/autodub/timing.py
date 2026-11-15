"""Per-line timing fit: stretch TTS into caption window (0.85–1.15×)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import soundfile as sf

from autodub.separate import SeparateError

MIN_RATIO = 0.85
MAX_RATIO = 1.15


@dataclass(frozen=True)
class FitResult:
    path: Path
    target_s: float
    tts_s: float
    stretch_ratio: float
    fit_ok: bool


def audio_duration_s(path: Path) -> float:
    info = sf.info(str(path))
    return float(info.duration)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise SeparateError("ffmpeg not found")
    return exe


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    data, sr = sf.read(str(src), always_2d=True)
    sf.write(str(dst), data, sr)


def fit_clip_to_window(in_path: Path, out_wav: Path, target_s: float) -> FitResult:
    """
    Compress TTS toward caption window when too long (atempo, clamped to 0.85–1.15).
    Shorter than target: copy as-is (mix pads with silence). 
    """
    in_path = Path(in_path)
    out_wav = Path(out_wav).with_suffix(".wav")
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    tts_s = audio_duration_s(in_path)
    target_s = max(0.05, float(target_s))

    if tts_s <= target_s * MAX_RATIO:
        _copy(in_path, out_wav)
        final = audio_duration_s(out_wav)
        ok = final <= target_s * MAX_RATIO
        return FitResult(out_wav, target_s, tts_s, 1.0, ok)

    desired = target_s / tts_s
    stretch_ratio = max(MIN_RATIO, min(MAX_RATIO, desired))
    tempo = stretch_ratio
    filters: list[str] = []
    while tempo < 0.5:
        filters.append("atempo=0.5")
        tempo /= 0.5
    while tempo > 2.0:
        filters.append("atempo=2.0")
        tempo /= 2.0
    filters.append(f"atempo={tempo:.6f}")

    cmd = [
        _ffmpeg(),
        "-y",
        "-i",
        str(in_path),
        "-af",
        ",".join(filters),
        str(out_wav),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        _copy(in_path, out_wav)
        final = audio_duration_s(out_wav)
        return FitResult(out_wav, target_s, tts_s, 1.0, final <= target_s * MAX_RATIO)

    final = audio_duration_s(out_wav)
    applied = final / tts_s if tts_s else 1.0
    ok = final <= target_s * MAX_RATIO
    return FitResult(out_wav, target_s, tts_s, applied, ok)
