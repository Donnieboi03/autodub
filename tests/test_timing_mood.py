from pathlib import Path

import numpy as np
import soundfile as sf

from autodub.mood import emotion_from_caption_text, resolve_emotion, settings_for_bucket
from autodub.timing import MAX_RATIO, MIN_RATIO, fit_clip_to_window


def test_emotion_punctuation_intense():
    assert emotion_from_caption_text("Look out!") == "intense"
    assert emotion_from_caption_text("WAIT FOR ME") == "intense"


def test_emotion_punctuation_calm():
    assert emotion_from_caption_text("Maybe later...") == "calm"


def test_settings_intense_higher_style():
    assert settings_for_bucket("intense").style > settings_for_bucket("calm").style


def test_fit_short_clip_ok(tmp_path: Path):
    sr = 22050
    # 0.5s tone into 1.0s window
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    wav = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    src = tmp_path / "in.wav"
    sf.write(str(src), wav, sr)
    out = tmp_path / "out.wav"
    result = fit_clip_to_window(src, out, target_s=1.0)
    assert result.fit_ok
    assert result.path.is_file()
    assert MIN_RATIO <= 1.0 <= MAX_RATIO


def test_resolve_emotion_wav_and_bang(tmp_path: Path):
    sr = 22050
    t = np.linspace(0, 0.3, int(sr * 0.3), endpoint=False)
    wav = (0.5 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
    path = tmp_path / "loud.wav"
    sf.write(str(path), wav, sr)
    emo = resolve_emotion(path, "Run!")
    assert emo.bucket in {"intense", "neutral", "calm"}
