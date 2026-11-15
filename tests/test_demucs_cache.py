"""Demucs stem cache keyed by media hash."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from autodub.cache import media_content_hash
from autodub.separate import try_demucs_vocals


def test_demucs_cache_hit_skips_subprocess(tmp_path: Path):
    full = tmp_path / "full.wav"
    full.write_bytes(b"fake-wav-bytes-1234")
    out_dir = tmp_path / "demucs"
    media_hash = media_content_hash(full)
    cached = out_dir / media_hash
    cached.mkdir(parents=True)
    (cached / "vocals.wav").write_bytes(b"v")
    (cached / "no_vocals.wav").write_bytes(b"n")

    with mock.patch("autodub.separate._demucs_argv", return_value=["demucs"]):
        with mock.patch("autodub.separate.subprocess.run") as run:
            result = try_demucs_vocals(full, out_dir)
            run.assert_not_called()
    assert result is not None
    vocals, no_vocals, cache_hit = result
    assert cache_hit is True
    assert vocals.read_bytes() == b"v"
    assert no_vocals.read_bytes() == b"n"


def test_demucs_writes_cache_after_run(tmp_path: Path):
    full = tmp_path / "full.wav"
    full.write_bytes(b"fake-wav-bytes-5678")
    out_dir = tmp_path / "demucs"
    media_hash = media_content_hash(full)

    def fake_run(cmd, capture_output, text, env):
        run_dir = Path(cmd[cmd.index("-o") + 1])
        stem_dir = run_dir / "htdemucs" / "full"
        stem_dir.mkdir(parents=True)
        (stem_dir / "vocals.wav").write_bytes(b"voc")
        (stem_dir / "no_vocals.wav").write_bytes(b"nov")
        return mock.Mock(returncode=0, stderr="")

    with mock.patch("autodub.separate._demucs_argv", return_value=["demucs"]):
        with mock.patch("autodub.separate.subprocess.run", side_effect=fake_run):
            result = try_demucs_vocals(full, out_dir)
    assert result is not None
    vocals, no_vocals, cache_hit = result
    assert cache_hit is False
    assert vocals == out_dir / media_hash / "vocals.wav"
    assert no_vocals == out_dir / media_hash / "no_vocals.wav"
    assert vocals.read_bytes() == b"voc"
