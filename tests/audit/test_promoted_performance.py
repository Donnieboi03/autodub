"""Promoted holdout greens — PerformanceCue predicates (M0.6)."""

from __future__ import annotations

import pytest

from .contract_rules import (
    PERFORMANCE_BUCKETS,
    PERFORMANCE_MANIFEST_REQUIRED_KEYS,
    el_controls_high_vs_low_arousal,
    loud_wav_maps_to_high_arousal_bucket,
    performance_bucket_valid,
    performance_manifest_object_holds,
    quiet_wav_maps_to_low_arousal_bucket,
)


def test_performance_bucket_set():
    assert PERFORMANCE_BUCKETS == {"whisper", "calm", "neutral", "intense", "shout"}


@pytest.mark.parametrize("bucket", ["whisper", "calm", "neutral", "intense", "shout"])
def test_bucket_valid(bucket: str):
    assert performance_bucket_valid(bucket)


def test_manifest_performance_keys():
    assert PERFORMANCE_MANIFEST_REQUIRED_KEYS == {
        "bucket",
        "arousal",
        "target_s",
        "stability",
        "style",
        "similarity_boost",
    }
    ok = {
        "bucket": "calm",
        "arousal": 0.2,
        "target_s": 1.0,
        "stability": 0.55,
        "style": 0.15,
        "similarity_boost": 0.7,
    }
    assert performance_manifest_object_holds(ok)
    bad = dict(ok)
    del bad["style"]
    assert not performance_manifest_object_holds(bad)


def test_el_controls_ordering_predicate():
    assert el_controls_high_vs_low_arousal(
        high_stability=0.25,
        high_style=0.75,
        low_stability=0.55,
        low_style=0.15,
    )


def test_loud_quiet_bucket_predicates():
    assert loud_wav_maps_to_high_arousal_bucket("shout")
    assert loud_wav_maps_to_high_arousal_bucket("intense")
    assert not loud_wav_maps_to_high_arousal_bucket("calm")
    assert quiet_wav_maps_to_low_arousal_bucket("calm")
    assert quiet_wav_maps_to_low_arousal_bucket("whisper")
    assert not quiet_wav_maps_to_low_arousal_bucket("shout")
