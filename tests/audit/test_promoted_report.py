"""Promoted holdout greens — episode report schema predicates."""

from __future__ import annotations

import pytest

from .contract_rules import (
    REPORT_REQUIRED_KEYS,
    REPORT_STAGES_MS_KEYS,
    episode_report_schema_holds,
    episode_report_spk_sim_holds,
)


def _valid_report() -> dict:
    return {
        "media": "m.mkv",
        "subs": "s.srt",
        "cast": "c.json",
        "mka": "o.mka",
        "model": "m",
        "me_method": "demucs",
        "stages_ms": {k: 0 for k in REPORT_STAGES_MS_KEYS},
        "chars_sent": 0,
        "cache_hits": 0,
        "lines": [],
        "fit_ok_ratio": 1.0,
        "est_credits": 0,
    }


def test_report_schema_keys_match_contract():
    assert "me_method" in REPORT_REQUIRED_KEYS
    assert "fit_ok_ratio" in REPORT_REQUIRED_KEYS
    assert "est_credits" in REPORT_REQUIRED_KEYS
    assert "demucs_or_me" in REPORT_STAGES_MS_KEYS


def test_valid_report_holds():
    assert episode_report_schema_holds(_valid_report())


@pytest.mark.parametrize("missing", ["media", "stages_ms", "fit_ok_ratio", "me_method"])
def test_report_rejects_missing_key(missing: str):
    report = _valid_report()
    del report[missing]
    assert not episode_report_schema_holds(report)


def test_spk_sim_optional_number_when_present():
    report = _valid_report()
    assert episode_report_spk_sim_holds(report)
    report["spk_sim"] = 0.5
    assert episode_report_spk_sim_holds(report)
    assert episode_report_schema_holds(report)
    report["spk_sim"] = "high"
    assert not episode_report_spk_sim_holds(report)
    assert not episode_report_schema_holds(report)
