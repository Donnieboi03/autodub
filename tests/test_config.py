from autodub.config import elevenlabs_key_present, load_env


def test_load_env_does_not_crash():
    load_env()


def test_key_present_is_bool():
    load_env()
    assert isinstance(elevenlabs_key_present(), bool)
