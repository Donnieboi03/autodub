"""Human+machine scorecard next to the episode report (settle gates G1–G9)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


def cast_method_histogram(manifest_lines: list[dict]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for line in manifest_lines:
        method = str(line.get("cast_method") or "unknown")
        counts[method] += 1
    return dict(sorted(counts.items()))


def write_scorecard(
    path: Path,
    report: dict[str, Any],
    *,
    manifest_lines: list[dict] | None = None,
) -> Path:
    """Write ADHD markdown scorecard; returns path."""
    path = Path(path)
    hist = report.get("cast_method_histogram")
    if hist is None and manifest_lines is not None:
        hist = cast_method_histogram(manifest_lines)
    hist = hist or {}
    hist_str = ", ".join(f"{k}={v}" for k, v in hist.items()) or "n/a"
    spk = report.get("spk_sim")
    spk_s = f"{spk:.4f}" if isinstance(spk, (int, float)) else "n/a"
    fit = report.get("fit_ok_ratio")
    fit_s = f"{fit:.4f}" if isinstance(fit, (int, float)) else "n/a"
    duck = report.get("duck_gain", "n/a")
    demucs_hit = report.get("demucs_cache_hit")
    demucs_s = str(demucs_hit) if demucs_hit is not None else "n/a"
    g3 = (
        "auto_pass"
        if isinstance(spk, (int, float)) and float(spk) >= 0.45
        else ("auto_fail" if isinstance(spk, (int, float)) else "pending")
    )
    g4 = (
        "auto_pass"
        if isinstance(fit, (int, float)) and float(fit) >= 0.9
        else ("auto_fail" if isinstance(fit, (int, float)) else "pending")
    )
    me = str(report.get("me_method") or "")
    g5 = "auto_pass" if me == "demucs" else ("auto_fail" if me else "pending")

    body = f"""# AutoDub scorecard

| Field | Value |
| --- | --- |
| model | {report.get("model", "n/a")} |
| me_method | {report.get("me_method", "n/a")} |
| duck_gain | {duck} |
| demucs_cache_hit | {demucs_s} |
| fit_ok_ratio | {fit_s} |
| cache_hits | {report.get("cache_hits", "n/a")} |
| chars_sent | {report.get("chars_sent", "n/a")} |
| est_credits | {report.get("est_credits", "n/a")} |
| spk_sim | {spk_s} |
| cast_method | {hist_str} |
| voice_fallback | {report.get("voice_fallback", "none")} |
| lines | {report.get("lines", "n/a")} |

## Settle gates G1–G9

| ID | Gate | Status |
| --- | --- | --- |
| G1 | Ear (show a friend) | pending |
| G2 | Cast (caption wins; unlabeled→jp_embed) | pending — hist: {hist_str} |
| G3 | SIM ≥ ~0.45 + G1 | {g3} (spk_sim={spk_s}) |
| G4 | Timing fit_ok_ratio ≥ 0.9 | {g4} |
| G5 | Bed demucs + duck | {g5} (me={me or "n/a"}, duck={duck}) |
| G6 | Emotion PerformanceCue buckets | pending |
| G7 | Cost ≥5 min logged | pending |
| G8 | Hygiene pytest + cache re-run | pending |
| G9 | Ethics no IVC in public git | pending |

Paste this table into chat when reporting a run.
"""
    path.write_text(body, encoding="utf-8")
    return path


def aggregate_score_run(out_dir: Path) -> dict[str, Any]:
    """Aggregate SIM + cast_method from a finished run directory."""
    import json

    out_dir = Path(out_dir)
    if not out_dir.is_dir():
        raise FileNotFoundError(f"run out dir not found: {out_dir}")
    reports = sorted(out_dir.glob("*.autodub.report.json"))
    if not reports:
        raise FileNotFoundError(f"no *.autodub.report.json under {out_dir}")
    report_path = reports[0]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifests = sorted(out_dir.glob("*.autodub.json"))
    lines: list[dict] = []
    if manifests:
        man = json.loads(manifests[0].read_text(encoding="utf-8"))
        lines = list(man.get("lines") or [])
    hist = report.get("cast_method_histogram") or cast_method_histogram(lines)
    return {
        "out": str(out_dir),
        "report": str(report_path),
        "spk_sim": report.get("spk_sim"),
        "cast_method_histogram": hist,
        "fit_ok_ratio": report.get("fit_ok_ratio"),
        "model": report.get("model"),
        "me_method": report.get("me_method"),
        "duck_gain": report.get("duck_gain"),
        "demucs_cache_hit": report.get("demucs_cache_hit"),
        "cache_hits": report.get("cache_hits"),
        "est_credits": report.get("est_credits"),
        "lines": report.get("lines"),
        "scorecard": str(next(out_dir.glob("*.autodub.scorecard.md"), "")),
    }
