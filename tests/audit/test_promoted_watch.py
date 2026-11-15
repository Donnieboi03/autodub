"""Promoted holdout greens — watch CLI fail-fast without media."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _autodub_argv() -> list[str]:
    """Console script beside the venv interpreter (avoid resolve→Frameworks)."""
    exe = Path(sys.executable)
    beside = exe.parent / "autodub"
    assert beside.is_file(), f"autodub console script missing next to {exe}"
    return [str(beside)]


def test_watch_subcommand_in_help():
    proc = subprocess.run(
        [*_autodub_argv(), "--help"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert proc.returncode == 0
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "watch" in combined


def test_watch_fails_fast_without_required_args():
    proc = subprocess.run(
        [*_autodub_argv(), "watch"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert proc.returncode != 0
    err = ((proc.stderr or "") + (proc.stdout or "")).lower()
    assert any(
        token in err
        for token in ("media", "required", "usage", "error", "missing", "subs", "cast")
    ), f"expected clear fail-fast message, got: {err!r}"


def test_watch_fails_fast_with_missing_media_path(
    tmp_path: Path, locked_cast_sheet: Path, synthetic_srt: Path
):
    missing = tmp_path / "absent.mkv"
    out = tmp_path / "out"
    out.mkdir()
    proc = subprocess.run(
        [
            *_autodub_argv(),
            "watch",
            "--media",
            str(missing),
            "--subs",
            str(synthetic_srt),
            "--cast",
            str(locked_cast_sheet),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert proc.returncode != 0
    err = ((proc.stderr or "") + (proc.stdout or "")).lower()
    assert "media" in err or "not found" in err or "fail" in err, (
        f"expected media-missing fail-fast message, got: {err!r}"
    )
