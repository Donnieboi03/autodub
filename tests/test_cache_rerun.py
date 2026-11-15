"""Re-run cache hits: same key → existing mp3 counts as cache_hit."""

from __future__ import annotations

from pathlib import Path

from autodub.cache import cache_key, cache_path, media_content_hash


def test_cache_key_ignores_whitespace_noise():
    a = cache_key("v1", "hello  world", "neutral", "m1")
    b = cache_key("v1", "hello world", "neutral", "m1")
    assert a == b


def test_rerun_hits_existing_render_cache(tmp_path: Path):
    root = tmp_path / "render_cache"
    key = cache_key("voiceA", "I'm gonna be King!", "neutral", "eleven_flash_v2")
    path = cache_path(root, key)
    path.write_bytes(b"fake-mp3")
    # Second lookup with equivalent text must see the file
    key2 = cache_key("voiceA", "I'm gonna be King!", "neutral", "eleven_flash_v2")
    assert key2 == key
    assert cache_path(root, key2).is_file()
    assert cache_path(root, key2).read_bytes() == b"fake-mp3"


def test_media_content_hash_stable(tmp_path: Path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF" + b"\0" * 100)
    assert media_content_hash(wav) == media_content_hash(wav)
    other = tmp_path / "b.wav"
    other.write_bytes(b"RIFF" + b"\1" * 100)
    assert media_content_hash(wav) != media_content_hash(other)
