from pathlib import Path

from autodub.paths import reportable_path


def test_reportable_path_relative_to_cwd(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "operator" / "runs" / "x" / "a.mka"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")
    assert reportable_path(target) == "operator/runs/x/a.mka"


def test_reportable_path_prefers_out_dir(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    media = out / "work" / "full.wav"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"x")
    assert reportable_path(media, out) == "work/full.wav"


def test_reportable_path_outside_stays_absolute(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "elsewhere_media.wav"
    # May or may not exist; resolve still works
    text = reportable_path(outside, tmp_path / "out")
    assert text.startswith("/") or text.startswith(str(tmp_path.parent))
