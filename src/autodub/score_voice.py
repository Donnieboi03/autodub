"""Speaker similarity soft gate (SpeechBrain ECAPA cosine + spectral fallback)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


class ScoreVoiceError(RuntimeError):
    pass


_verifier = None


def _load_verifier():
    global _verifier
    if _verifier is not None:
        return _verifier
    try:
        from speechbrain.inference.speaker import SpeakerRecognition
    except ImportError as exc:
        raise ScoreVoiceError(
            "speechbrain not installed — pip install 'autodub[score]' "
            "(or: pip install speechbrain torch)"
        ) from exc
    _verifier = SpeakerRecognition.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(Path.home() / ".cache" / "autodub" / "spkrec-ecapa-voxceleb"),
    )
    return _verifier


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two 1-D vectors (clipped to [-1, 1])."""
    av = np.asarray(a, dtype=np.float64).ravel()
    bv = np.asarray(b, dtype=np.float64).ravel()
    if av.size == 0 or bv.size == 0:
        return 0.0
    n = min(av.size, bv.size)
    av = av[:n]
    bv = bv[:n]
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denom < 1e-12:
        return 0.0
    return float(np.clip(np.dot(av, bv) / denom, -1.0, 1.0))


def spectral_fingerprint(wav: Path | str, *, n_bands: int = 32) -> np.ndarray:
    """Lightweight log-magnitude band fingerprint (tests / SpeechBrain fallback)."""
    path = Path(wav)
    if not path.is_file():
        raise ScoreVoiceError(f"wav not found: {path}")
    audio, _sr = sf.read(str(path), always_2d=True)
    mono = audio.mean(axis=1).astype(np.float64)
    if mono.size < 16:
        return np.zeros(n_bands, dtype=np.float64)
    mono = mono - mono.mean()
    window = np.hanning(mono.size)
    spec = np.abs(np.fft.rfft(mono * window))
    spec = np.log1p(spec)
    # Average into fixed bands so different lengths still compare.
    edges = np.linspace(0, spec.size, n_bands + 1, dtype=int)
    bands = np.zeros(n_bands, dtype=np.float64)
    for i in range(n_bands):
        lo, hi = edges[i], edges[i + 1]
        if hi <= lo:
            continue
        bands[i] = float(spec[lo:hi].mean())
    norm = float(np.linalg.norm(bands))
    if norm < 1e-12:
        return bands
    return bands / norm


def spectral_similarity(ref_wav: Path | str, hyp_wav: Path | str) -> float:
    """Cosine of spectral fingerprints — distinct tones separate cleanly in tests."""
    return cosine_similarity(
        spectral_fingerprint(ref_wav),
        spectral_fingerprint(hyp_wav),
    )


def score_similarity(ref_wav: Path | str, hyp_wav: Path | str) -> float:
    """Return cosine similarity score between two wavs (higher ≈ same speaker)."""
    ref = Path(ref_wav)
    hyp = Path(hyp_wav)
    if not ref.is_file():
        raise ScoreVoiceError(f"ref not found: {ref}")
    if not hyp.is_file():
        raise ScoreVoiceError(f"hyp not found: {hyp}")
    verifier = _load_verifier()
    score, _prediction = verifier.verify_files(str(ref), str(hyp))
    # speechbrain may return tensor
    try:
        return float(score)
    except TypeError:
        return float(score.item())
