"""Audio extract and M&E stem: demucs / audio-separator / stereotools fallback."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class SeparateError(RuntimeError):
    pass


@dataclass(frozen=True)
class MeStemResult:
    path: Path
    method: str  # demucs | audio_separator | stereotools | volume


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
    Not studio Demucs — fallback when ML separators are absent.
    """
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
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


def _demucs_argv() -> list[str] | None:
    """Resolve demucs CLI even when only the project venv is on PATH."""
    which = shutil.which("demucs")
    if which:
        return [which]
    sibling = Path(sys.executable).resolve().parent / "demucs"
    if sibling.exists():
        return [str(sibling)]
    try:
        import demucs  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "demucs"]


def try_demucs_vocals(full_wav: Path, out_dir: Path) -> tuple[Path, Path] | None:
    """If demucs is available, return (vocals, no_vocals). Else None."""
    argv = _demucs_argv()
    if not argv:
        return None
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *argv,
        "-n",
        "htdemucs",
        "--two-stems=vocals",
        "-o",
        str(out_dir),
        str(full_wav),
    ]
    # Prefer MPS/CPU; demucs picks device. Keep env for operator overrides.
    env = os.environ.copy()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        return None
    found_v = list(out_dir.rglob("vocals.wav"))
    found_nv = list(out_dir.rglob("no_vocals.wav"))
    if found_v and found_nv:
        return found_v[0], found_nv[0]
    return None


def try_audio_separator_instrumental(
    full_wav: Path,
    out_dir: Path,
    *,
    model_filename: str | None = None,
) -> Path | None:
    """
    Optional UVR/MelBand path via python-audio-separator.
    Returns instrumental/M&E wav path, or None if package/model unavailable.
    """
    try:
        from audio_separator.separator import Separator
    except ImportError:
        return None

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model = model_filename or os.environ.get(
        "AUTODUB_SEPARATOR_MODEL",
        "UVR_MDXNET_KARA_2.onnx",
    )
    model_dir = Path(
        os.environ.get(
            "AUTODUB_SEPARATOR_MODEL_DIR",
            str(Path.home() / ".cache" / "autodub" / "audio-separator-models"),
        )
    )
    model_dir.mkdir(parents=True, exist_ok=True)
    try:
        separator = Separator(
            model_file_dir=str(model_dir),
            output_dir=str(out_dir),
            output_format="wav",
            output_single_stem="Instrumental",
        )
        separator.load_model(model_filename=model)
        outputs = separator.separate(str(full_wav))
    except Exception:
        return None
    if not outputs:
        return None
    # separate() returns list of output paths (str)
    candidates = [Path(p) for p in outputs]
    for path in candidates:
        name = path.name.lower()
        if "instrumental" in name or "no_vocals" in name or "karaoke" in name:
            if path.is_file():
                return path
    for path in candidates:
        if path.is_file():
            return path
    return None


def resolve_me_stem(
    full_wav: Path,
    work_dir: Path,
    *,
    prefer: str | None = None,
) -> MeStemResult:
    """
    Prefer real vocal removal when optional deps work; else stereotools approx.

    Order (default): demucs htdemucs two-stems → audio-separator Instrumental → stereotools.
    Override with prefer=demucs|audio_separator|stereotools or AUTODUB_ME_METHOD.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    method = (prefer or os.environ.get("AUTODUB_ME_METHOD") or "auto").strip().lower()

    def _demucs() -> MeStemResult | None:
        pair = try_demucs_vocals(full_wav, work_dir / "demucs")
        if not pair:
            return None
        _vocals, no_vocals = pair
        return MeStemResult(path=no_vocals, method="demucs")

    def _separator() -> MeStemResult | None:
        instrumental = try_audio_separator_instrumental(
            full_wav, work_dir / "audio_separator"
        )
        if not instrumental:
            return None
        return MeStemResult(path=instrumental, method="audio_separator")

    def _approx() -> MeStemResult:
        out = approximate_me_stem(full_wav, work_dir / "me.wav")
        # detect which af succeeded by peeking at file (always me.wav)
        return MeStemResult(path=out, method="stereotools")

    if method == "stereotools":
        return _approx()
    if method == "demucs":
        return _demucs() or _approx()
    if method in {"audio_separator", "separator", "uvr"}:
        return _separator() or _approx()

    # auto
    return _demucs() or _separator() or _approx()


def separator_status() -> dict[str, bool | str]:
    """Doctor-friendly capability report (no model download)."""
    demucs_ok = _demucs_argv() is not None
    try:
        import audio_separator  # noqa: F401

        separator_ok = True
    except ImportError:
        separator_ok = False
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "demucs": demucs_ok,
        "audio_separator": separator_ok,
        "default_me_order": "demucs → audio_separator → stereotools",
    }
