from autodub.cast_sheet import CastSheet, VoiceBinding
from autodub.pipeline import _stock_fallback_voice


def test_stock_fallback_when_voice_id_missing():
    cast = CastSheet(
        path=__import__("pathlib").Path("x.json"),
        schema_version=1,
        show_title="T",
        season=1,
        bindings=[
            VoiceBinding("narrator", "Narrator", "elevenlabs", "stockvid", None),
            VoiceBinding("luffy", "Luffy", "elevenlabs", None, "refs/luffy.wav"),
        ],
    )
    binding = cast.bindings[1]
    fixed, used = _stock_fallback_voice(cast, binding)
    assert used is True
    assert fixed.voice_id == "stockvid"
    assert fixed.character_id == "luffy"
    assert fixed.ref_wav == "refs/luffy.wav"


def test_no_fallback_when_voice_present():
    cast = CastSheet(
        path=__import__("pathlib").Path("x.json"),
        schema_version=1,
        show_title="T",
        season=1,
        bindings=[
            VoiceBinding("luffy", "Luffy", "elevenlabs", "vid1", None),
        ],
    )
    fixed, used = _stock_fallback_voice(cast, cast.bindings[0])
    assert used is False
    assert fixed.voice_id == "vid1"
