"""Mix EN dialogue chunks onto an M&E bed; export wav then mka via ffmpeg."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from autodub.separate import SeparateError

# M&E gain under active dialogue (was 0.2 — bed nearly inaudible on listen).
# 0.45 keeps bed listenable while dialogue stays intelligible at dialogue_peak.
ME_DUCK_GAIN = 0.45


@dataclass
class TimedClip:
    start_s: float
    path: Path
    text: str
    character_id: str


def _load_mono(path: Path, sr: int) -> np.ndarray:
    audio, file_sr = sf.read(str(path), always_2d=True)
    mono = audio.mean(axis=1).astype(np.float32)
    if file_sr != sr:
        # linear resample
        duration = mono.shape[0] / file_sr
        n = int(duration * sr)
        x_old = np.linspace(0.0, 1.0, num=mono.shape[0], endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=max(n, 1), endpoint=False)
        mono = np.interp(x_new, x_old, mono).astype(np.float32)
    return mono


def mix_to_wav(
    me_wav: Path,
    clips: list[TimedClip],
    out_wav: Path,
    *,
    sample_rate: int = 44100,
    dialogue_peak: float = 0.35,
) -> Path:
    me = _load_mono(Path(me_wav), sample_rate)
    total = me.shape[0]
    dialogue = np.zeros(total, dtype=np.float32)

    for clip in clips:
        start = int(clip.start_s * sample_rate)
        if start >= total:
            continue
        piece = _load_mono(Path(clip.path), sample_rate)
        # peak normalize piece
        peak = float(np.max(np.abs(piece)) + 1e-9)
        piece = piece * (dialogue_peak / peak)
        end = min(total, start + piece.shape[0])
        dialogue[start:end] += piece[: end - start]
        # duck ME under dialogue region
        duck_end = end
        me[start:duck_end] *= ME_DUCK_GAIN

    mixed = np.clip(me + dialogue, -1.0, 1.0)
    # stereo
    stereo = np.stack([mixed, mixed], axis=1)
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), stereo, sample_rate)
    return out_wav


def wav_to_mka(wav: Path, out_mka: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SeparateError("ffmpeg not found")
    out_mka = Path(out_mka)
    out_mka.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(wav),
        "-c:a",
        "libopus",
        "-b:a",
        "128k",
        str(out_mka),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SeparateError(proc.stderr[-400:] or "mka encode failed")
    return out_mka


def write_run_manifest(path: Path, payload: dict) -> Path:
    path = Path(path)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path
