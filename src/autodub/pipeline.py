"""File pipeline: captions + cast → TTS → timing fit → mix → mka + report."""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from autodub.cache import cache_key, cache_path
from autodub.captions import load_captions, normalize_script_text
from autodub.cast_sheet import CastSheet, VoiceBinding, load_cast_sheet
from autodub.config import elevenlabs_tts_model, load_env
from autodub.elevenlabs_client import ElevenLabsError, tts_to_file
from autodub.events import emit
from autodub.mix import TimedClip, mix_to_wav, wav_to_mka, write_run_manifest
from autodub.mood import resolve_emotion
from autodub.separate import extract_wav, resolve_me_stem, slice_wav
from autodub.timing import fit_clip_to_window

_SPEAKER_PREFIX = re.compile(r"^([A-Za-z][A-Za-z0-9 _'-]{0,40}):\s+(.*)$")

# Flash ≈ 0.5–1 credit/char on subscription; report uses 1.0 as conservative est
_CREDITS_PER_CHAR = 1.0


def _resolve_binding(text: str, cast: CastSheet) -> tuple[VoiceBinding, str]:
    by_name = {b.name.lower(): b for b in cast.bindings}
    by_id = cast.by_character_id()
    m = _SPEAKER_PREFIX.match(text)
    if m:
        name, body = m.group(1), m.group(2)
        key = name.lower()
        if key in by_name:
            return by_name[key], body
        cid = name.lower().replace(" ", "_")
        if cid in by_id:
            return by_id[cid], body
    # unknown / no prefix → prefer narrator/unknown binding if present
    for pref in ("unknown", "narrator", "_guest"):
        if pref in by_id:
            return by_id[pref], text
        for b in cast.bindings:
            if b.name.lower() == pref:
                return b, text
    default = cast.default_voice()
    if not default:
        raise RuntimeError("cast sheet has no usable voice")
    return default, text


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


def run_file_pipeline(
    media: Path,
    subs: Path,
    cast_path: Path,
    out_dir: Path,
    *,
    max_workers: int = 4,
    limit_lines: int | None = None,
    allow_caption_trim: bool = False,
) -> dict:
    load_env()
    media = Path(media)
    subs = Path(subs)
    cast_path = Path(cast_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

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
    stages_ms["demucs_or_me"] = (time.perf_counter() - t0) * 1000.0
    emit("me_stem_ready", method=me.method, path=str(me_wav))

    model = elevenlabs_tts_model()
    clips: list[TimedClip] = []
    manifest_lines: list[dict] = []
    def render_one(cap_index: int) -> tuple[TimedClip, dict, int, int, int]:
        """Returns clip, meta, chars_sent_delta, cache_hit_delta, fit_ok_delta."""
        cap = captions[cap_index]
        binding, script = _resolve_binding(cap.text, cast)
        target_s = max(0.05, cap.end_s - cap.start_s)
        script = normalize_script_text(script)
        script, text_source = _maybe_trim_caption(script, target_s, allow_caption_trim)
        if not binding.voice_id:
            raise ElevenLabsError(f"no voice_id for character {binding.character_id}")

        slice_path = work / f"slice_{cap.index:04d}.wav"
        slice_wav(full_wav, slice_path, cap.start_s, min(cap.end_s, cap.start_s + 2.5))
        emo = resolve_emotion(slice_path, script)
        key = cache_key(binding.voice_id, script, emo.bucket, model)
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
                stability=emo.stability,
                similarity_boost=emo.similarity_boost,
                style=emo.style,
            )
            chars_delta = len(script)
            emit(
                "line_rendered",
                character_id=binding.character_id,
                index=cap.index,
                chars=len(script),
                emotion=emo.bucket,
            )
        emit(
            "cast_matched",
            character_id=binding.character_id,
            index=cap.index,
            confidence=1.0 if _SPEAKER_PREFIX.match(cap.text) else 0.5,
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
            "emotion": emo.bucket,
            "cache_hit": hit,
            "audio": str(fitted.path),
            "target_s": fitted.target_s,
            "tts_s": fitted.tts_s,
            "stretch_ratio": fitted.stretch_ratio,
            "fit_ok": fitted.fit_ok,
        }
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
        )

    t0 = time.perf_counter()
    chars_sent = 0
    cache_hits = 0
    fit_ok_n = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = [pool.submit(render_one, i) for i in range(len(captions))]
        for fut in as_completed(futs):
            clip, meta, cdelta, hdelta, fdelta = fut.result()
            clips.append(clip)
            manifest_lines.append(meta)
            chars_sent += cdelta
            cache_hits += hdelta
            fit_ok_n += fdelta
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

    manifest_path = out_dir / f"{media.stem}.autodub.json"
    write_run_manifest(
        manifest_path,
        {
            "media": str(media),
            "subs": str(subs),
            "cast": str(cast_path),
            "mka": str(out_mka),
            "model": model,
            "me_method": me.method,
            "lines": manifest_lines,
        },
    )

    report = {
        "media": str(media),
        "subs": str(subs),
        "cast": str(cast_path),
        "mka": str(out_mka),
        "model": model,
        "me_method": me.method,
        "stages_ms": stages_ms,
        "chars_sent": chars_sent,
        "cache_hits": cache_hits,
        "lines": len(manifest_lines),
        "fit_ok_ratio": round(fit_ok_ratio, 4),
        "est_credits": est_credits,
    }
    report_path = out_dir / f"{media.stem}.autodub.report.json"
    write_run_manifest(report_path, report)

    return {
        "mka": str(out_mka),
        "manifest": str(manifest_path),
        "report": str(report_path),
        "lines": len(manifest_lines),
        "me_method": me.method,
        "fit_ok_ratio": fit_ok_ratio,
        "est_credits": est_credits,
    }
