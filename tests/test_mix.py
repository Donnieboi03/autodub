import numpy as np
import soundfile as sf
from pathlib import Path

from autodub.mix import ME_DUCK_GAIN, TimedClip, mix_to_wav


def test_me_duck_gain_documented():
    # Listenable bed under dialogue; was 0.2 (too quiet on OP listen).
    assert 0.35 <= ME_DUCK_GAIN <= 0.55


def test_mix_ducks_me_under_dialogue(tmp_path: Path):
    sr = 8000
    me = np.ones(sr, dtype=np.float32)  # 1s of 1.0
    me_path = tmp_path / "me.wav"
    sf.write(str(me_path), me, sr)
    clip_audio = np.full(int(0.2 * sr), 0.5, dtype=np.float32)
    clip_path = tmp_path / "clip.wav"
    sf.write(str(clip_path), clip_audio, sr)
    out = mix_to_wav(
        me_path,
        [TimedClip(start_s=0.1, path=clip_path, text="hi", character_id="x")],
        tmp_path / "mixed.wav",
        sample_rate=sr,
        dialogue_peak=0.35,
    )
    mixed, file_sr = sf.read(str(out), always_2d=True)
    assert file_sr == sr
    # Outside duck window ME≈1; under dialogue ME is attenuated before add.
    # Spot-check mid-dialogue sample is not pure silence and not unducked 1.0+.
    mid = int(0.15 * sr)
    sample = float(mixed[mid, 0])
    assert abs(sample) > 0.05
    assert abs(sample) < 0.95
