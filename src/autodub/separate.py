"""Audio extract and M&E approximation (ffmpeg). Optional demucs if installed."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class SeparateError(RuntimeError):
    pass


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise SeparateError("ffmpeg not found on PATH")
    return exe


def extract_wav(media: Path, out_wav: Path, *, sample_rate: int = 44100) -> Path:
    media = Path(media)
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _ffmpeg(),
        "-y",
        "-i",
        str(media),
        "-ac",
        "2",
        "-ar",
        str(sample_rate),
        "-vn",
        str(out_wav),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SeparateError(proc.stderr[-500:] or "ffmpeg extract failed")
    return out_wav


def slice_wav(in_wav: Path, out_wav: Path, start_s: float, end_s: float) -> Path:
    """Cut a time slice for mood / guest ref."""
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.05, end_s - start_s)
    cmd = [
        _ffmpeg(),
        "-y",
        "-ss",
        f"{start_s:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(in_wav),
        str(out_wav),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SeparateError(proc.stderr[-400:] or "ffmpeg slice failed")
    return out_wav


def approximate_me_stem(full_wav: Path, out_wav: Path) -> Path:
    """
    Approximate music/effects by attenuating center (dialogue-heavy) channel.
    Not studio Demucs — good enough for v1 file mix when demucs absent.
    """
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    # extrastereo then mix: pull center down
    af = "stereotools=mlev=0.15"
    cmd = [
        _ffmpeg(),
        "-y",
        "-i",
        str(full_wav),
        "-af",
        af,
        str(out_wav),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # fallback: quiet the whole bed slightly
        cmd = [
            _ffmpeg(),
            "-y",
            "-i",
            str(full_wav),
            "-af",
            "volume=0.25",
            str(out_wav),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise SeparateError(proc.stderr[-400:] or "me stem failed")
    return out_wav


def try_demucs_vocals(full_wav: Path, out_dir: Path) -> tuple[Path, Path] | None:
    """If demucs CLI available, return (vocals, no_vocals). Else None."""
    if not shutil.which("demucs"):
        return None
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "demucs",
        "-n",
        "htdemucs",
        "--two-stems=vocals",
        "-o",
        str(out_dir),
        str(full_wav),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    # demucs writes out_dir/htdemucs/<stem>/<name>.wav
    found_v = list(out_dir.rglob("vocals.wav"))
    found_nv = list(out_dir.rglob("no_vocals.wav"))
    if found_v and found_nv:
        return found_v[0], found_nv[0]
    return None
