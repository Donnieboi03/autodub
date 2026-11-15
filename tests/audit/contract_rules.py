"""Promoted from holdout — pure CONTRACT predicates."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


def whitespace_normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def caption_fidelity_holds(caption_text: str, spoken_or_script_text: str, *, normalize) -> bool:
    return normalize(caption_text) == normalize(spoken_or_script_text)


def cast_lock_stable(character_id: str, voice_by_character: Mapping[str, str | None]) -> str:
    if character_id not in voice_by_character:
        raise KeyError(f"character_id not locked: {character_id}")
    voice_id = voice_by_character[character_id]
    if not voice_id:
        raise ValueError(f"locked character has empty voice_id: {character_id}")
    return voice_id


# CONTRACT §Rules.4 — Timing fit
STRETCH_RATIO_MIN = 0.85
STRETCH_RATIO_MAX = 1.15


def stretch_ratio_in_contract_band(stretch_ratio: float) -> bool:
    return STRETCH_RATIO_MIN <= float(stretch_ratio) <= STRETCH_RATIO_MAX


def fit_ok_matches_duration_band(
    *,
    fit_ok: bool,
    final_duration_s: float,
    target_duration_s: float,
) -> bool:
    if target_duration_s <= 0:
        return not fit_ok
    ratio = float(final_duration_s) / float(target_duration_s)
    in_band = stretch_ratio_in_contract_band(ratio)
    return bool(fit_ok) is in_band


def line_or_report_timing_fields_hold(obj: Mapping[str, Any]) -> bool:
    if "stretch_ratio" in obj:
        if not stretch_ratio_in_contract_band(float(obj["stretch_ratio"])):
            return False
    if obj.get("fit_ok") is True and "stretch_ratio" in obj:
        if not stretch_ratio_in_contract_band(float(obj["stretch_ratio"])):
            return False
    if (
        "fit_ok" in obj
        and "final_duration_s" in obj
        and "target_duration_s" in obj
    ):
        if not fit_ok_matches_duration_band(
            fit_ok=bool(obj["fit_ok"]),
            final_duration_s=float(obj["final_duration_s"]),
            target_duration_s=float(obj["target_duration_s"]),
        ):
            return False
    return True


# CONTRACT §Rules.5 — PerformanceCue predicates (M0.6, promoted thin subset)
PERFORMANCE_BUCKETS = frozenset({"whisper", "calm", "neutral", "intense", "shout"})
HIGH_AROUSAL_BUCKETS = frozenset({"intense", "shout"})
LOW_AROUSAL_BUCKETS = frozenset({"calm", "whisper"})
PERFORMANCE_MANIFEST_REQUIRED_KEYS = frozenset(
    {
        "bucket",
        "arousal",
        "target_s",
        "stability",
        "style",
        "similarity_boost",
    }
)


def performance_bucket_valid(bucket: Any) -> bool:
    return isinstance(bucket, str) and bucket.strip().lower() in PERFORMANCE_BUCKETS


def performance_manifest_object_holds(performance: Mapping[str, Any]) -> bool:
    if not PERFORMANCE_MANIFEST_REQUIRED_KEYS.issubset(performance.keys()):
        return False
    if not performance_bucket_valid(performance.get("bucket")):
        return False
    for key in ("arousal", "target_s", "stability", "style", "similarity_boost"):
        val = performance.get(key)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return False
    return True


def el_controls_high_vs_low_arousal(
    *,
    high_stability: float,
    high_style: float,
    low_stability: float,
    low_style: float,
) -> bool:
    return float(high_stability) < float(low_stability) and float(high_style) > float(
        low_style
    )


def loud_wav_maps_to_high_arousal_bucket(bucket: str) -> bool:
    return isinstance(bucket, str) and bucket.strip().lower() in HIGH_AROUSAL_BUCKETS


def quiet_wav_maps_to_low_arousal_bucket(bucket: str) -> bool:
    return isinstance(bucket, str) and bucket.strip().lower() in LOW_AROUSAL_BUCKETS


# CONTRACT §Episode report schema
REPORT_REQUIRED_KEYS = frozenset(
    {
        "media",
        "subs",
        "cast",
        "mka",
        "model",
        "me_method",
        "stages_ms",
        "chars_sent",
        "cache_hits",
        "lines",
        "fit_ok_ratio",
        "est_credits",
    }
)

REPORT_STAGES_MS_KEYS = frozenset(
    {
        "extract",
        "demucs_or_me",
        "tts",
        "fit",
        "mix",
        "encode",
    }
)


def episode_report_has_required_keys(report: Mapping[str, Any]) -> bool:
    return REPORT_REQUIRED_KEYS.issubset(report.keys())


def episode_report_stages_ms_complete(report: Mapping[str, Any]) -> bool:
    stages = report.get("stages_ms")
    if not isinstance(stages, Mapping):
        return False
    return REPORT_STAGES_MS_KEYS.issubset(stages.keys())


def episode_report_spk_sim_holds(report: Mapping[str, Any]) -> bool:
    if "spk_sim" not in report:
        return True
    val = report["spk_sim"]
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def episode_report_schema_holds(report: Mapping[str, Any]) -> bool:
    if not episode_report_has_required_keys(report):
        return False
    if not episode_report_stages_ms_complete(report):
        return False
    if not isinstance(report.get("lines"), Sequence) or isinstance(
        report.get("lines"), (str, bytes)
    ):
        return False
    if not episode_report_spk_sim_holds(report):
        return False
    return True


REQUIRED_EVENTS = frozenset(
    {
        "line_rendered",
        "cast_matched",
        "cache_hit",
        "overlay_underrun",
        "audio_tap_unavailable",
        "me_stem_ready",
        "performance_resolved",
    }
)
