"""Unit tests: IVC caption-verify gate (window match / mismatch / missing subs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from autodub.captions import load_captions
from autodub.voices import (
    CaptionVerifyError,
    character_id_from_name,
    verify_ivc_caption_window,
)


def _write_srt(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_character_id_from_name_slug():
    assert character_id_from_name("Luffy") == "luffy"
    assert character_id_from_name("luffy-en-dub") == "luffy_en_dub"


def test_caption_window_match_speaker_prefix(tmp_path: Path):
    srt = _write_srt(
        tmp_path / "ok.srt",
        """1
00:00:14,000 --> 00:00:20,000
Luffy: I'm gonna be King of the Pirates!

2
00:00:30,000 --> 00:00:32,000
Zoro: Got it.
""",
    )
    matched = verify_ivc_caption_window(
        srt, character_id="luffy", start_s=14.0, end_s=24.0
    )
    assert len(matched) == 1
    assert matched[0].text.startswith("Luffy:")


def test_caption_window_match_via_loaded_lines(tmp_path: Path):
    srt = _write_srt(
        tmp_path / "ok.srt",
        """1
00:00:10,000 --> 00:00:12,000
Luffy: Meat!
""",
    )
    caps = load_captions(srt)
    matched = verify_ivc_caption_window(
        caps, character_id="LUFFY", start_s=9.5, end_s=11.0
    )
    assert len(matched) == 1


def test_caption_window_fail_speaker_mismatch(tmp_path: Path):
    srt = _write_srt(
        tmp_path / "mismatch.srt",
        """1
00:00:14,000 --> 00:00:20,000
Zoro: Three swords.
""",
    )
    with pytest.raises(CaptionVerifyError, match="caption-verify failed"):
        verify_ivc_caption_window(
            srt, character_id="luffy", start_s=14.0, end_s=24.0
        )


def test_caption_window_fail_no_speaker_labels(tmp_path: Path):
    srt = _write_srt(
        tmp_path / "nolabel.srt",
        """1
00:00:14,000 --> 00:00:20,000
Just crowd noise line.
""",
    )
    with pytest.raises(CaptionVerifyError, match="caption-verify failed"):
        verify_ivc_caption_window(
            srt, character_id="luffy", start_s=14.0, end_s=24.0
        )


def test_caption_window_fail_no_overlap(tmp_path: Path):
    srt = _write_srt(
        tmp_path / "elsewhere.srt",
        """1
00:01:00,000 --> 00:01:02,000
Luffy: Later.
""",
    )
    with pytest.raises(CaptionVerifyError, match="caption-verify failed"):
        verify_ivc_caption_window(
            srt, character_id="luffy", start_s=14.0, end_s=24.0
        )


def test_caption_window_fail_missing_subs(tmp_path: Path):
    missing = tmp_path / "nope.srt"
    with pytest.raises(CaptionVerifyError, match="caption-verify failed"):
        verify_ivc_caption_window(
            missing, character_id="luffy", start_s=0.0, end_s=1.0
        )


def test_caption_window_match_ass_style(tmp_path: Path):
    ass = tmp_path / "style.ass"
    ass.write_text(
        """[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Luffy,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:14.00,0:00:18.00,Luffy,,0,0,0,,I'm hungry!
""",
        encoding="utf-8",
    )
    matched = verify_ivc_caption_window(
        ass, character_id="luffy", start_s=14.0, end_s=24.0
    )
    assert len(matched) == 1
    assert matched[0].style.lower() == "luffy"


def test_cli_ivc_requires_subs():
    from autodub.cli import main

    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "voices",
                "ivc",
                "--name",
                "luffy",
                "--media",
                "/tmp/does-not-matter.mp4",
                "--start",
                "0",
                "--end",
                "1",
            ]
        )
    assert excinfo.value.code == 2
