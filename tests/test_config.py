from autodub.config import elevenlabs_key_present, elevenlabs_tts_model, load_env


def test_load_env_does_not_crash():
    load_env()


def test_key_present_is_bool():
    load_env()
    assert isinstance(elevenlabs_key_present(), bool)


def test_autodub_tts_model_overrides_elevenlabs(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")
    monkeypatch.setenv("AUTODUB_TTS_MODEL", "eleven_multilingual_v2")
    assert elevenlabs_tts_model() == "eleven_multilingual_v2"
    monkeypatch.delenv("AUTODUB_TTS_MODEL")
    assert elevenlabs_tts_model() == "eleven_flash_v2_5"
