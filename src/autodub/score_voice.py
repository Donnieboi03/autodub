"""Speaker similarity soft gate (SpeechBrain ECAPA cosine)."""

from __future__ import annotations

from pathlib import Path


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
