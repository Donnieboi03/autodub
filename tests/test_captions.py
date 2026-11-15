from pathlib import Path

from autodub.captions import load_captions, normalize_script_text


def test_normalize_script_text_whitespace():
    assert normalize_script_text("  hello   world\n") == "hello world"


def test_load_srt_speaker_prefixed(tmp_path: Path):
    srt = tmp_path / "t.srt"
    srt.write_text(
        """1
00:00:01,000 --> 00:00:02,000
Luffy: Hello there!

2
00:00:03,000 --> 00:00:04,000
Zoro: Move.
""",
        encoding="utf-8",
    )
    lines = load_captions(srt)
    assert len(lines) == 2
    assert lines[0].text == "Luffy: Hello there!"
    assert lines[0].start_s == 1.0
    assert abs(lines[0].end_s - 2.0) < 1e-6
    assert lines[1].text.startswith("Zoro:")


def test_load_captions_missing_fails(tmp_path: Path):
    try:
        load_captions(tmp_path / "nope.srt")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
