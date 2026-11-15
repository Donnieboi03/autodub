from pathlib import Path

import numpy as np
import soundfile as sf

from autodub.performance import el_controls_for_bucket, resolve_performance


def test_el_shout_higher_style_lower_stability():
    shout_s, _, shout_st = el_controls_for_bucket("shout")
    calm_s, _, calm_st = el_controls_for_bucket("calm")
    assert shout_st > calm_st
    assert shout_s < calm_s


def _write_tone(path: Path, *, amp: float, seconds: float = 0.4, sr: int = 22050) -> None:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    wav = (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sf.write(str(path), wav, sr)


def test_loud_wav_and_bang_escalates(tmp_path: Path):
    path = tmp_path / "loud.wav"
    _write_tone(path, amp=0.55)
    cue = resolve_performance(path, "Look out!", target_s=1.0, source="vocals")
    assert cue.bucket in {"intense", "shout"}
    assert cue.style >= el_controls_for_bucket("neutral")[2]
    assert cue.source == "vocals"
    assert cue.target_s == 1.0
    d = cue.to_dict()
    assert "arousal" in d and "stability" in d


def test_quiet_wav_calm_or_whisper(tmp_path: Path):
    path = tmp_path / "quiet.wav"
    _write_tone(path, amp=0.008)
    cue = resolve_performance(path, "maybe later...", target_s=2.0, source="mix_fallback")
    assert cue.bucket in {"calm", "whisper", "neutral"}
    assert cue.source == "mix_fallback"
    assert cue.style <= el_controls_for_bucket("intense")[2]


def test_score_voice_fail_fast_missing_files(tmp_path: Path):
    from autodub.cli import main

    code = main(
        [
            "score-voice",
            "--ref",
            str(tmp_path / "missing_ref.wav"),
            "--hyp",
            str(tmp_path / "missing_hyp.wav"),
        ]
    )
    assert code == 2
