from pathlib import Path

from autodub.cast_sheet import load_cast_sheet, write_cast_sheet


def test_roundtrip_cast_sheet(tmp_path: Path):
    path = tmp_path / "show.cast.json"
    write_cast_sheet(
        path,
        {
            "schema_version": 1,
            "show": {"title": "Example", "season": 2},
            "bindings": [
                {
                    "character_id": "lead",
                    "name": "Lead",
                    "voice": {"backend": "elevenlabs", "voice_id": "abc"},
                }
            ],
        },
    )
    sheet = load_cast_sheet(path)
    assert sheet.show_title == "Example"
    assert sheet.season == 2
    assert sheet.bindings[0].voice_id == "abc"
    assert sheet.by_character_id()["lead"].name == "Lead"
    assert sheet.default_voice().character_id == "lead"


def test_empty_bindings_fail(tmp_path: Path):
    path = tmp_path / "empty.json"
    path.write_text('{"schema_version":1,"show":{},"bindings":[]}\n')
    try:
        load_cast_sheet(path)
        assert False, "expected ValueError"
    except ValueError:
        pass
