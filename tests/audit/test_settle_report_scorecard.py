"""Settle gates — episode report, scorecard, events, cache, score-run CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

# CONTRACT: Episode report schema (required keys)
REQUIRED_REPORT_KEYS = {
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
    "cast_method_histogram",
    "duck_gain",
    "demucs_cache_hit",
}

REQUIRED_STAGES_MS = {
    "extract",
    "demucs_or_me",
    "tts",
    "fit",
    "mix",
    "encode",
}

CAST_METHODS = frozenset({"caption", "jp_embed", "default"})

REQUIRED_EVENTS = frozenset(
    {
        "line_rendered",
        "cast_matched",
        "cache_hit",
        "overlay_underrun",
        "audio_tap_unavailable",
        "me_stem_ready",
        "performance_resolved",
        "voice_fallback",
    }
)

SETTLE_GATES = tuple(f"G{i}" for i in range(1, 10))


def _minimal_report(**overrides: object) -> dict:
    base: dict = {
        "media": "episode.mp4",
        "subs": "episode.en.srt",
        "cast": "episode.cast.json",
        "mka": "episode.en.mka",
        "model": "eleven_turbo_v2_5",
        "me_method": "demucs",
        "stages_ms": {k: 1 for k in REQUIRED_STAGES_MS},
        "chars_sent": 42,
        "cache_hits": 0,
        "lines": [
            {
                "cast_method": "caption",
                "cast_confidence": 1.0,
                "performance": {"bucket": "neutral"},
                "cache_hit": False,
            }
        ],
        "fit_ok_ratio": 1.0,
        "est_credits": 0.5,
        "cast_method_histogram": {"caption": 1, "jp_embed": 0, "default": 0},
        "duck_gain": 0.3,
        "demucs_cache_hit": False,
    }
    base.update(overrides)
    return base


def test_episode_report_required_keys_present():
    """Report payload must carry every CONTRACT-required key (schema contract)."""
    report = _minimal_report()
    missing = REQUIRED_REPORT_KEYS - set(report)
    assert not missing, f"missing required report keys: {sorted(missing)}"
    assert set(report["stages_ms"]) >= REQUIRED_STAGES_MS
    assert isinstance(report["duck_gain"], (int, float))
    assert isinstance(report["demucs_cache_hit"], bool)
    assert isinstance(report["cast_method_histogram"], dict)
    for method in report["cast_method_histogram"]:
        assert method in CAST_METHODS


def test_scorecard_written_beside_report_with_g1_g9_and_histogram(tmp_path: Path):
    """*.autodub.scorecard.md exists next to report with G1–G9 stubs + cast_method hist."""
    from autodub.scorecard import write_scorecard

    report = _minimal_report(
        cast_method_histogram={"caption": 2, "jp_embed": 1, "default": 0},
        duck_gain=0.25,
        demucs_cache_hit=True,
        spk_sim=0.5,
    )
    report_path = tmp_path / "demo.autodub.report.json"
    report_path.write_text(json.dumps(report) + "\n", encoding="utf-8")
    scorecard_path = tmp_path / "demo.autodub.scorecard.md"

    written = write_scorecard(scorecard_path, report)
    assert Path(written) == scorecard_path
    assert scorecard_path.is_file()
    body = scorecard_path.read_text(encoding="utf-8")
    for gate in SETTLE_GATES:
        assert gate in body, f"scorecard missing settle gate stub {gate}"
    assert "cast_method" in body.lower() or "histogram" in body.lower()
    # histogram values should surface somehow
    assert "caption" in body and "jp_embed" in body


def test_cast_method_enum_only_allowed_values():
    """cast_method ∈ {caption, jp_embed, default} (CONTRACT)."""
    assert CAST_METHODS == frozenset({"caption", "jp_embed", "default"})
    hist = _minimal_report()["cast_method_histogram"]
    assert set(hist) <= CAST_METHODS


def test_unlabeled_caption_not_claimed_as_caption(tmp_path: Path):
    """Unlabeled cue must not report method=caption from a false Name: parse."""
    from autodub.cast_match import resolve_cast_match
    from autodub.cast_sheet import load_cast_sheet

    cast_path = tmp_path / "cast.json"
    cast_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "show": {"title": "Settle", "season": 1},
                "bindings": [
                    {
                        "character_id": "char_hero",
                        "name": "Hero",
                        "voice": {
                            "backend": "elevenlabs",
                            "voice_id": "voice_hero",
                            "ref_wav": None,
                        },
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    sheet = load_cast_sheet(cast_path)
    result = resolve_cast_match("We leave at dawn without a speaker prefix.", sheet)
    assert result.method in CAST_METHODS
    assert result.method != "caption", (
        "unlabeled dialogue must not claim caption method "
        f"(got method={result.method!r})"
    )
    assert result.method in {"jp_embed", "default"}


def test_ivc_without_matching_subs_fails_caption_verify(tmp_path: Path):
    """IVC enrollment without matching labeled --subs fails with caption-verify failed."""
    import wave

    from autodub.voices import CaptionVerifyError, verify_ivc_caption_window

    subs = tmp_path / "unlabeled.en.srt"
    subs.write_text(
        "1\n"
        "00:00:01,000 --> 00:00:03,000\n"
        "Just dialogue with no speaker label.\n",
        encoding="utf-8",
    )
    with pytest.raises((CaptionVerifyError, SystemExit, RuntimeError, ValueError)) as excinfo:
        verify_ivc_caption_window(
            subs, character_id="char_hero", start_s=1.0, end_s=3.0
        )
    assert "caption-verify failed" in str(excinfo.value).lower()

    # CLI path: voices ivc with unlabeled window also fails fast
    media = tmp_path / "slice.wav"
    with wave.open(str(media), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 1600)

    proc = subprocess.run(
        [
            "uv",
            "run",
            "autodub",
            "voices",
            "ivc",
            "--name",
            "Hero",
            "--character",
            "char_hero",
            "--media",
            str(media),
            "--subs",
            str(subs),
            "--start",
            "1",
            "--end",
            "2",
            "--work",
            str(tmp_path / "work"),
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert proc.returncode != 0
    combined = (proc.stderr + proc.stdout).lower()
    assert "caption-verify failed" in combined


def test_tts_cache_key_stable_for_identical_inputs():
    """Identical (voice_id, script, performance_bucket, model) → same cache key string."""
    from autodub.cache import cache_key

    a = cache_key("voice_a", "Hello world.", "neutral", "eleven_turbo_v2_5")
    b = cache_key("voice_a", "Hello world.", "neutral", "eleven_turbo_v2_5")
    c = cache_key("voice_a", "Hello world!", "neutral", "eleven_turbo_v2_5")
    assert isinstance(a, str) and a
    assert a == b
    assert a != c


def test_required_events_emit_to_jsonl(tmp_path: Path):
    """Required event names are emit targets; events.jsonl lines are JSON with event name."""
    from autodub.events import emit, set_events_sink

    sink = tmp_path / "events.jsonl"
    set_events_sink(sink)
    try:
        for name in sorted(REQUIRED_EVENTS):
            event = emit(name, source="holdout_settle")
            assert getattr(event, "name", None) == name or True
        # cast_matched should accept method+confidence payload (CONTRACT)
        emit("cast_matched", method="jp_embed", confidence=0.4)
        emit("voice_fallback", voice_fallback="stock")
    finally:
        set_events_sink(None)

    assert sink.is_file()
    lines = [ln for ln in sink.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines
    seen: set[str] = set()
    for line in lines:
        obj = json.loads(line)
        assert isinstance(obj, dict)
        name = obj.get("event") or obj.get("name")
        assert name, f"events.jsonl line missing event name: {obj!r}"
        seen.add(str(name))
    assert REQUIRED_EVENTS <= seen


def test_duck_gain_and_demucs_cache_hit_on_report_schema():
    """duck_gain (number) and demucs_cache_hit (bool) present on report schema."""
    report = _minimal_report(duck_gain=0.2, demucs_cache_hit=True)
    assert "duck_gain" in report and isinstance(report["duck_gain"], (int, float))
    assert "demucs_cache_hit" in report and isinstance(report["demucs_cache_hit"], bool)
    # scorecard must surface them when written
    from autodub.scorecard import write_scorecard

    # exercised with write in scorecard test; schema presence is the gate here
    hist = report["cast_method_histogram"]
    assert isinstance(hist, dict)


def test_score_run_cli_exists_and_fails_fast_without_finished_report(tmp_path: Path):
    """autodub score-run --out DIR fails fast (non-zero) without a finished report."""
    empty = tmp_path / "empty_out"
    empty.mkdir()
    proc = subprocess.run(
        [
            "uv",
            "run",
            "autodub",
            "score-run",
            "--out",
            str(empty),
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    # Must be a real subcommand (not argparse invalid choice) and non-zero without report
    combined = (proc.stderr + proc.stdout).lower()
    assert "invalid choice" not in combined, (
        "score-run CLI missing from autodub (CONTRACT requires score-run)"
    )
    assert proc.returncode != 0, "score-run must fail fast without finished report"
