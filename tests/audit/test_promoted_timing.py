"""Promoted holdout greens — timing fit predicates (0.85–1.15)."""

from __future__ import annotations

import pytest

from .contract_rules import (
    STRETCH_RATIO_MAX,
    STRETCH_RATIO_MIN,
    fit_ok_matches_duration_band,
    line_or_report_timing_fields_hold,
    stretch_ratio_in_contract_band,
)


def test_stretch_band_constants():
    assert STRETCH_RATIO_MIN == 0.85
    assert STRETCH_RATIO_MAX == 1.15


@pytest.mark.parametrize(
    "ratio,ok",
    [(0.85, True), (1.0, True), (1.15, True), (0.84, False), (1.16, False)],
)
def test_stretch_ratio_band(ratio, ok):
    assert stretch_ratio_in_contract_band(ratio) is ok


def test_fit_ok_duration_consistency():
    assert fit_ok_matches_duration_band(
        fit_ok=True, final_duration_s=1.0, target_duration_s=1.0
    )
    assert not fit_ok_matches_duration_band(
        fit_ok=True, final_duration_s=0.5, target_duration_s=1.0
    )


def test_line_timing_fields_when_present():
    assert line_or_report_timing_fields_hold({"fit_ok": True, "stretch_ratio": 1.1})
    assert not line_or_report_timing_fields_hold({"fit_ok": True, "stretch_ratio": 2.0})
    assert line_or_report_timing_fields_hold({"text": "no timing fields"})
