"""File pipeline: captions + cast → TTS → timing fit → mix → mka + report.

Dual-source (CONTRACT): EN caption sidecar owns spoken words; speaker identity
comes from caption ``Name:`` / ASS style when present, else **cast_matcher**
(JP vocals slice ↔ cast ``ref_wav`` bank). JP never overrides an explicit
caption speaker prefix. Soft ``score-voice`` never replaces caption-verify for
IVC enrollment.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from autodub.cache import cache_key, cache_path
from autodub.captions import load_captions, normalize_script_text
from autodub.cast_match import resolve_cast_match
from autodub.cast_sheet import CastSheet, VoiceBinding, load_cast_sheet
from autodub.config import elevenlabs_tts_model, load_env
from autodub.elevenlabs_client import ElevenLabsError, tts_to_file
from autodub.events import emit, set_events_sink
from autodub.mix import ME_DUCK_GAIN, TimedClip, mix_to_wav, wav_to_mka, write_run_manifest
from autodub.paths import reportable_path
from autodub.performance import resolve_performance
from autodub.score_voice import ScoreVoiceError, score_similarity
from autodub.scorecard import cast_method_histogram, write_scorecard
from autodub.separate import extract_wav, resolve_me_stem, slice_wav
from autodub.timing import fit_clip_to_window

# Flash ≈ 0.5–1 credit/char on subscription; report uses 1.0 as conservative est
_CREDITS_PER_CHAR = 1.0


def _resolve_binding(text: str, cast: CastSheet) -> tuple[VoiceBinding, str]:
    """Caption-only resolve (tests / callers without a vocals slice)."""
    result = resolve_cast_match(text, cast, vocals_slice=None)
    return result.binding, result.script


def _stock_fallback_voice(cast: CastSheet, binding: VoiceBinding) -> tuple[VoiceBinding, bool]:
    """If binding has no voice_id, reuse first stock voice on the sheet."""
    if binding.voice_id:
        return binding, False
    for b in cast.bindings:
        if b.voice_id:
            return (
                VoiceBinding(
                    character_id=binding.character_id,
                    name=binding.name,
                    backend=b.backend,
                    voice_id=b.voice_id,
                    ref_wav=binding.ref_wav,
                ),
                True,
            )
    raise ElevenLabsError(
        f"no voice_id for character {binding.character_id} and no stock fallback on cast"
    )


def _maybe_trim_caption(script: str, target_s: float, allow_trim: bool) -> tuple[str, str]:
    """Rough trim: ~14 chars/sec speaking rate. Returns text, text_source."""
    if not allow_trim:
        return script, "caption"
    # estimate chars that fit at ~13 cps
    budget = max(8, int(target_s * 13))
    if len(script) <= budget:
        return script, "caption"
    trimmed = script[: budget - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    if len(trimmed) < 4:
        return script, "caption"
    return trimmed, "caption_trimmed"


def _resolve_role_ref(cast: CastSheet, character_id: str, score_ref: Path | None) -> Path | None:
    if score_ref is not None and Path(score_ref).is_file():
        return Path(score_ref)
    for b in cast.bindings:
        if b.character_id != character_id:
            continue
        if not b.ref_wav or b.ref_wav == "from_line_slice":
            continue
        candidate = Path(b.ref_wav)
        if not candidate.is_file():
            candidate = (cast.path.parent / b.ref_wav).resolve()
        if candidate.is_file():
            return candidate
    for b in cast.bindings:
        if not b.ref_wav or b.ref_wav == "from_line_slice":
            continue
        candidate = Path(b.ref_wav)
        if not candidate.is_file():
            candidate = (cast.path.parent / b.ref_wav).resolve()
        if candidate.is_file():
            return candidate
    return None


def _auto_spk_sim(
    cast: CastSheet,
    manifest_lines: list[dict],
    *,
    score_ref: Path | None,
) -> float | None:
    """Mean soft SIM: role ref_wav (or --score-ref) vs fitted line audio when present."""
    if not manifest_lines:
        return None
    scores: list[float] = []
    for meta in manifest_lines:
        hyp = Path(meta.get("audio") or "")
        if not hyp.is_file():
            continue
        ref = _resolve_role_ref(cast, str(meta.get("character_id") or ""), score_ref)
        if ref is None:
            continue
        try:
            scores.append(float(score_similarity(ref, hyp)))
            meta["spk_sim"] = scores[-1]
        except ScoreVoiceError:
            continue
    if not scores:
        return None
    return sum(scores) / len(scores)


def run_file_pipeline(
    media: Path,
    subs: Path,
    cast_path: Path,
    out_dir: Path,
    *,
    max_workers: int = 4,
    limit_lines: int | None = None,
    allow_caption_trim: bool = False,
    score_ref: Path | None = None,
) -> dict:
    load_env()
    media = Path(media)
    subs = Path(subs)
    cast_path = Path(cast_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    set_events_sink(out_dir / "events.jsonl")

    try:
        if not media.is_file():
            raise FileNotFoundError(f"media not found: {media}")
        if not subs.is_file():
            raise FileNotFoundError(f"subs not found: {subs}")

        stages_ms: dict[str, float] = {}
        cast = load_cast_sheet(cast_path)
        captions = load_captions(subs)
        if limit_lines is not None:
            captions = captions[:limit_lines]
        if not captions:
            raise RuntimeError("no caption lines after filtering")

        work = out_dir / "work"
        cache_root = out_dir / "render_cache"
        work.mkdir(exist_ok=True)

        t0 = time.perf_counter()
        full_wav = extract_wav(media, work / "full.wav")
        stages_ms["extract"] = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        me = resolve_me_stem(full_wav, work)
        me_wav = me.path
        vocals_wav = me.vocals_path
        stages_ms["demucs_or_me"] = (time.perf_counter() - t0) * 1000.0
        emit(
            "me_stem_ready",
            method=me.method,
            path=str(me_wav),
            vocals=str(vocals_wav) if vocals_wav else None,
            cache_hit=me.demucs_cache_hit,
        )

        analysis_root = vocals_wav if (vocals_wav and Path(vocals_wav).is_file()) else full_wav
        performance_source = "vocals" if analysis_root == vocals_wav else "mix_fallback"

        model = elevenlabs_tts_model()
        clips: list[TimedClip] = []
        manifest_lines: list[dict] = []
        voice_fallback_stock = False

        def render_one(cap_index: int) -> tuple[TimedClip, dict, int, int, int, bool]:
            """Returns clip, meta, chars_sent_delta, cache_hit_delta, fit_ok_delta, stock_fallback."""
            cap = captions[cap_index]
            slice_path = work / f"slice_{cap.index:04d}.wav"
            target_s = max(0.05, cap.end_s - cap.start_s)
            slice_end = min(cap.end_s, cap.start_s + max(target_s, 0.5))
            slice_wav(analysis_root, slice_path, cap.start_s, slice_end)

            match = resolve_cast_match(
                cap.text,
                cast,
                vocals_slice=slice_path,
            )
            binding = match.binding
            script = match.script
            binding, used_stock = _stock_fallback_voice(cast, binding)
            script = normalize_script_text(script)
            script, text_source = _maybe_trim_caption(script, target_s, allow_caption_trim)
            if not binding.voice_id:
                raise ElevenLabsError(f"no voice_id for character {binding.character_id}")

            cue = resolve_performance(
                slice_path,
                script,
                target_s=target_s,
                source=performance_source,
            )
            emit(
                "performance_resolved",
                character_id=binding.character_id,
                index=cap.index,
                bucket=cue.bucket,
                source=cue.source,
                arousal=cue.arousal,
            )
            key = cache_key(binding.voice_id, script, cue.bucket, model)
            raw_mp3 = cache_path(cache_root, key)
            hit = raw_mp3.is_file()
            chars_delta = 0
            hit_delta = 0
            if hit:
                emit("cache_hit", character_id=binding.character_id, key=key)
                hit_delta = 1
            else:
                tts_to_file(
                    script,
                    binding.voice_id,
                    raw_mp3,
                    model_id=model,
                    stability=cue.stability,
                    similarity_boost=cue.similarity_boost,
                    style=cue.style,
                )
                chars_delta = len(script)
                emit(
                    "line_rendered",
                    character_id=binding.character_id,
                    index=cap.index,
                    chars=len(script),
                    emotion=cue.bucket,
                )
            emit(
                "cast_matched",
                character_id=binding.character_id,
                index=cap.index,
                confidence=match.confidence,
                method=match.method,
            )

            fitted = fit_clip_to_window(
                raw_mp3, work / f"fit_{cap.index:04d}.wav", target_s
            )
            fit_delta = 1 if fitted.fit_ok else 0

            meta = {
                "index": cap.index,
                "start_s": cap.start_s,
                "end_s": cap.end_s,
                "text": script,
                "text_source": text_source,
                "source_caption": cap.text,
                "character_id": binding.character_id,
                "voice_id": binding.voice_id,
                "cast_method": match.method,
                "cast_confidence": match.confidence,
                "emotion": cue.bucket,
                "performance": cue.to_dict(),
                "cache_hit": hit,
                "audio": reportable_path(fitted.path, out_dir),
                "target_s": fitted.target_s,
                "tts_s": fitted.tts_s,
                "stretch_ratio": fitted.stretch_ratio,
                "fit_ok": fitted.fit_ok,
            }
            if used_stock:
                meta["voice_fallback"] = "stock"
                emit(
                    "voice_fallback",
                    character_id=binding.character_id,
                    index=cap.index,
                    reason="stock",
                )
            return (
                TimedClip(
                    start_s=cap.start_s,
                    path=fitted.path,
                    text=script,
                    character_id=binding.character_id,
                ),
                meta,
                chars_delta,
                hit_delta,
                fit_delta,
                used_stock,
            )

        t0 = time.perf_counter()
        chars_sent = 0
        cache_hits = 0
        fit_ok_n = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = [pool.submit(render_one, i) for i in range(len(captions))]
            for fut in as_completed(futs):
                clip, meta, cdelta, hdelta, fdelta, stock = fut.result()
                clips.append(clip)
                manifest_lines.append(meta)
                chars_sent += cdelta
                cache_hits += hdelta
                fit_ok_n += fdelta
                voice_fallback_stock = voice_fallback_stock or stock
        stages_ms["tts"] = (time.perf_counter() - t0) * 1000.0
        stages_ms["fit"] = stages_ms["tts"] * 0.15

        clips.sort(key=lambda c: c.start_s)
        manifest_lines.sort(key=lambda m: m["index"])

        t0 = time.perf_counter()
        mixed_wav = mix_to_wav(me_wav, clips, work / "mixed.wav")
        stages_ms["mix"] = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        out_mka = wav_to_mka(mixed_wav, out_dir / f"{media.stem}.autodub.mka")
        stages_ms["encode"] = (time.perf_counter() - t0) * 1000.0

        fit_ok_ratio = (fit_ok_n / len(manifest_lines)) if manifest_lines else 0.0
        est_credits = chars_sent * _CREDITS_PER_CHAR
        hist = cast_method_histogram(manifest_lines)

        rel_media = reportable_path(media, out_dir)
        rel_subs = reportable_path(subs, out_dir)
        rel_cast = reportable_path(cast_path, out_dir)
        rel_mka = reportable_path(out_mka, out_dir)

        manifest_path = out_dir / f"{media.stem}.autodub.json"
        write_run_manifest(
            manifest_path,
            {
                "media": rel_media,
                "subs": rel_subs,
                "cast": rel_cast,
                "mka": rel_mka,
                "model": model,
                "me_method": me.method,
                "lines": manifest_lines,
            },
        )

        report = {
            "media": rel_media,
            "subs": rel_subs,
            "cast": rel_cast,
            "mka": rel_mka,
            "model": model,
            "me_method": me.method,
            "stages_ms": stages_ms,
            "chars_sent": chars_sent,
            "cache_hits": cache_hits,
            "lines": len(manifest_lines),
            "fit_ok_ratio": round(fit_ok_ratio, 4),
            "est_credits": est_credits,
            "cast_method_histogram": hist,
            "duck_gain": ME_DUCK_GAIN,
            "demucs_cache_hit": bool(me.demucs_cache_hit),
        }
        if voice_fallback_stock:
            report["voice_fallback"] = "stock"

        want_score = score_ref is not None or any(
            b.ref_wav and b.ref_wav != "from_line_slice" for b in cast.bindings
        )
        if want_score:
            # Prefer absolute audio paths for scoring (manifest stores relative).
            score_lines = []
            for meta in manifest_lines:
                audio = Path(meta["audio"])
                if not audio.is_file():
                    audio = out_dir / meta["audio"]
                score_lines.append({**meta, "audio": str(audio)})
            spk = _auto_spk_sim(cast, score_lines, score_ref=score_ref)
            if spk is not None:
                report["spk_sim"] = spk
                # Mirror per-line spk_sim onto the written manifest lines.
                for src, dst in zip(score_lines, manifest_lines, strict=False):
                    if "spk_sim" in src:
                        dst["spk_sim"] = src["spk_sim"]
                write_run_manifest(
                    manifest_path,
                    {
                        "media": rel_media,
                        "subs": rel_subs,
                        "cast": rel_cast,
                        "mka": rel_mka,
                        "model": model,
                        "me_method": me.method,
                        "lines": manifest_lines,
                    },
                )

        report_path = out_dir / f"{media.stem}.autodub.report.json"
        write_run_manifest(report_path, report)
        scorecard_path = out_dir / f"{media.stem}.autodub.scorecard.md"
        write_scorecard(scorecard_path, report, manifest_lines=manifest_lines)

        return {
            "mka": rel_mka,
            "manifest": reportable_path(manifest_path, out_dir),
            "report": reportable_path(report_path, out_dir),
            "scorecard": reportable_path(scorecard_path, out_dir),
            "lines": len(manifest_lines),
            "me_method": me.method,
            "fit_ok_ratio": fit_ok_ratio,
            "est_credits": est_credits,
            "cache_hits": cache_hits,
            "cast_method_histogram": hist,
            "duck_gain": ME_DUCK_GAIN,
            "demucs_cache_hit": bool(me.demucs_cache_hit),
        }
    finally:
        set_events_sink(None)
