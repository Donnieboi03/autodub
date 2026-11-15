from pathlib import Path

from autodub.cast_sheet import write_cast_sheet, load_cast_sheet
from autodub.pipeline import _resolve_binding


def test_resolve_speaker_prefix(tmp_path: Path):
    path = tmp_path / "c.json"
    write_cast_sheet(
        path,
        {
            "schema_version": 1,
            "show": {"title": "T", "season": 1},
            "bindings": [
                {
                    "character_id": "luffy",
                    "name": "Luffy",
                    "voice": {"backend": "elevenlabs", "voice_id": "vid1"},
                },
                {
                    "character_id": "zoro",
                    "name": "Zoro",
                    "voice": {"backend": "elevenlabs", "voice_id": "vid2"},
                },
            ],
        },
    )
    cast = load_cast_sheet(path)
    b, body = _resolve_binding("Luffy: I'm gonna be King!", cast)
    assert b.character_id == "luffy"
    assert body == "I'm gonna be King!"
    b2, body2 = _resolve_binding("No prefix line", cast)
    assert b2.character_id == "luffy"  # default
    assert body2 == "No prefix line"
