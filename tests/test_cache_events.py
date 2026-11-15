import json

from autodub.cache import cache_key, cache_path
from autodub.events import emit


def test_cache_key_stable_and_distinct(tmp_path):
    a = cache_key("v1", "hello", "neutral", "m1")
    b = cache_key("v1", "hello", "neutral", "m1")
    c = cache_key("v1", "hello!", "neutral", "m1")
    assert a == b
    assert a != c
    p = cache_path(tmp_path / "c", a)
    assert p.name.endswith(".mp3")
    assert p.parent.is_dir()


def test_emit_event_shape(capsys):
    ev = emit("line_rendered", character_id="x", index=1)
    assert ev.name == "line_rendered"
    err = capsys.readouterr().err
    payload = json.loads(err.strip())
    assert payload["event"] == "line_rendered"
    assert payload["character_id"] == "x"
