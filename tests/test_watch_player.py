"""Unit tests for watch player argv builder (no media playback)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from autodub.cli import build_watch_player_argv


def test_build_watch_player_argv_prefers_mpv(tmp_path: Path):
    media = tmp_path / "clip.mp4"
    mka = tmp_path / "clip.autodub.mka"
    media.write_bytes(b"x")
    mka.write_bytes(b"y")
    out = tmp_path / "out"
    argv = build_watch_player_argv(
        media,
        mka,
        out_dir=out,
        player_path="/usr/local/bin/mpv",
    )
    assert argv == ["/usr/local/bin/mpv", f"--audio-file={mka}", str(media)]


def test_build_watch_player_argv_ffplay_remuxes_then_plays(tmp_path: Path):
    media = tmp_path / "clip.mp4"
    mka = tmp_path / "clip.autodub.mka"
    media.write_bytes(b"x")
    mka.write_bytes(b"y")
    out = tmp_path / "out"
    fake_ffmpeg = "/opt/homebrew/bin/ffmpeg"
    with patch("autodub.cli.subprocess.check_call") as check_call:
        argv = build_watch_player_argv(
            media,
            mka,
            out_dir=out,
            player_path="/opt/homebrew/bin/ffplay",
            ffmpeg_path=fake_ffmpeg,
        )
    temp_mp4 = out / "clip.autodub.watch.mp4"
    assert argv == ["/opt/homebrew/bin/ffplay", "-autoexit", str(temp_mp4)]
    remux = check_call.call_args[0][0]
    assert remux[0] == fake_ffmpeg
    assert "-y" in remux
    assert remux.count("-i") == 2
    assert str(media) in remux
    assert str(mka) in remux
    assert "-map" in remux and "0:v:0" in remux and "1:a:0" in remux
    assert "-c:v" in remux and "copy" in remux
    assert "-c:a" in remux and "aac" in remux
    assert str(temp_mp4) == remux[-1]
    # ffplay itself must not receive dual -i
    assert argv.count("-i") == 0


def test_build_watch_player_argv_ffplay_needs_ffmpeg(tmp_path: Path):
    media = tmp_path / "clip.mp4"
    mka = tmp_path / "clip.autodub.mka"
    media.write_bytes(b"x")
    mka.write_bytes(b"y")
    with (
        patch("autodub.cli.shutil.which", return_value=None),
        pytest.raises(FileNotFoundError, match="ffmpeg"),
    ):
        build_watch_player_argv(
            media,
            mka,
            out_dir=tmp_path / "out",
            player_path="/opt/homebrew/bin/ffplay",
            ffmpeg_path=None,
        )


def test_build_watch_player_argv_missing_player(tmp_path: Path):
    media = tmp_path / "clip.mp4"
    mka = tmp_path / "clip.autodub.mka"
    media.write_bytes(b"x")
    mka.write_bytes(b"y")
    with (
        patch("autodub.cli.shutil.which", return_value=None),
        pytest.raises(FileNotFoundError, match="mpv or ffplay"),
    ):
        build_watch_player_argv(
            media,
            mka,
            out_dir=tmp_path / "out",
            player_path=None,
        )
