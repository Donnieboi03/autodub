"""Resolve cast binding: caption speaker label wins; else JP vocals ↔ ref bank.

When EN captions lack a machine-readable speaker (``Name:`` / ASS style), match
the JP/source vocals slice against cast ``ref_wav`` banks via speaker embedding
cosine (SpeechBrain ECAPA when installed; spectral fingerprint fallback).
Explicit caption labels are never overridden by JP similarity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from autodub.cast_sheet import CastSheet, VoiceBinding
from autodub.score_voice import ScoreVoiceError, score_similarity, spectral_similarity

# Soft gate — calibrated later against labeled JP slices. Above → accept jp_embed.
JP_EMBED_THRESHOLD = 0.25

_SPEAKER_PREFIX = re.compile(r"^([A-Za-z][A-Za-z0-9 _'-]{0,40}):\s+(.*)$")

# Prefer these when unlabeled / below threshold (never steal a main-cast voice).
_DEFAULT_IDS = ("unknown", "narrator", "_guest")


@dataclass(frozen=True)
class CastMatchResult:
    binding: VoiceBinding
    script: str
    method: str  # caption | jp_embed | default
    confidence: float
    scores: dict[str, float] | None = None


def _default_binding(cast: CastSheet) -> VoiceBinding:
    by_id = cast.by_character_id()
    for pref in _DEFAULT_IDS:
        if pref in by_id:
            return by_id[pref]
        for b in cast.bindings:
            if b.name.lower() == pref:
                return b
    default = cast.default_voice()
    if not default:
        raise RuntimeError("cast sheet has no usable voice")
    return default


def _matchable_refs(cast: CastSheet, *, cast_dir: Path) -> list[tuple[VoiceBinding, Path]]:
    """Bindings with an existing ref_wav (relative paths resolve against cast file dir)."""
    out: list[tuple[VoiceBinding, Path]] = []
    for b in cast.bindings:
        if b.character_id in _DEFAULT_IDS:
            continue
        if not b.ref_wav or b.ref_wav == "from_line_slice":
            continue
        ref = Path(b.ref_wav)
        if not ref.is_file():
            ref = (cast_dir / b.ref_wav).resolve()
        if ref.is_file():
            out.append((b, ref))
    return out


def _similarity(ref: Path, hyp: Path) -> float:
    try:
        return float(score_similarity(ref, hyp))
    except ScoreVoiceError:
        return float(spectral_similarity(ref, hyp))


def resolve_cast_match(
    text: str,
    cast: CastSheet,
    *,
    vocals_slice: Path | str | None = None,
    threshold: float = JP_EMBED_THRESHOLD,
    similarity_fn=None,
) -> CastMatchResult:
    """Pick voice binding + spoken script for one caption line.

    Priority:
    1. ``Name:`` prefix (or id slug) → method ``caption``, confidence 1.0
    2. Else if vocals slice + cast refs → best cosine ≥ threshold → ``jp_embed``
    3. Else unknown/narrator/guest/default → ``default``
    """
    by_name = {b.name.lower(): b for b in cast.bindings}
    by_id = cast.by_character_id()
    cast_dir = cast.path.parent if cast.path else Path(".")

    m = _SPEAKER_PREFIX.match(text)
    if m:
        name, body = m.group(1), m.group(2)
        key = name.lower()
        if key in by_name:
            return CastMatchResult(
                binding=by_name[key],
                script=body,
                method="caption",
                confidence=1.0,
            )
        cid = name.lower().replace(" ", "_")
        if cid in by_id:
            return CastMatchResult(
                binding=by_id[cid],
                script=body,
                method="caption",
                confidence=1.0,
            )
        # Prefixed but unknown name — keep body, fall through with default voice
        text = body

    sim_fn = similarity_fn or _similarity
    slice_path = Path(vocals_slice) if vocals_slice else None
    if slice_path is not None and slice_path.is_file():
        refs = _matchable_refs(cast, cast_dir=cast_dir)
        if refs:
            scores: dict[str, float] = {}
            best_binding: VoiceBinding | None = None
            best_score = float("-inf")
            for binding, ref in refs:
                score = float(sim_fn(ref, slice_path))
                scores[binding.character_id] = score
                if score > best_score:
                    best_score = score
                    best_binding = binding
            if best_binding is not None and best_score >= threshold:
                return CastMatchResult(
                    binding=best_binding,
                    script=text,
                    method="jp_embed",
                    confidence=float(best_score),
                    scores=scores,
                )
            return CastMatchResult(
                binding=_default_binding(cast),
                script=text,
                method="default",
                confidence=float(best_score) if best_binding is not None else 0.0,
                scores=scores,
            )

    return CastMatchResult(
        binding=_default_binding(cast),
        script=text,
        method="default",
        confidence=0.0,
    )


# Back-compat alias used by older tests / callers
def resolve_binding(text: str, cast: CastSheet) -> tuple[VoiceBinding, str]:
    result = resolve_cast_match(text, cast, vocals_slice=None)
    return result.binding, result.script
