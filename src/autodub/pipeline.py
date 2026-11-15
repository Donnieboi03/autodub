"""File pipeline: captions + cast → TTS chunks → mix → mka."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from autodub.cache import cache_key, cache_path
from autodub.captions import load_captions, normalize_script_text
from autodub.cast_sheet import CastSheet, VoiceBinding, load_cast_sheet
from autodub.config import elevenlabs_tts_model, load_env
from autodub.elevenlabs_client import ElevenLabsError, tts_to_file
from autodub.events import emit
from autodub.mix import TimedClip, mix_to_wav, wav_to_mka, write_run_manifest
from autodub.mood import emotion_bucket_from_wav, style_for_bucket
from autodub.separate import extract_wav, resolve_me_stem, slice_wav

_SPEAKER_PREFIX = re.compile(r"^([A-Za-z][A-Za-z0-9 _'-]{0,40}):\s+(.*)$")


def _resolve_binding(text: str, cast: CastSheet) -> tuple[VoiceBinding, str]:
    """Return binding + script text (prefix stripped). Caption-faithful body text."""
    by_name = {b.name.lower(): b for b in cast.bindings}
    by_id = cast.by_character_id()
    m = _SPEAKER_PREFIX.match(text)
    if m:
        name, body = m.group(1), m.group(2)
        key = name.lower()
        if key in by_name:
            return by_name[key], body
        # try character_id
        cid = name.lower().replace(" ", "_")
        if cid in by_id:
            return by_id[cid], body
    default = cast.default_voice()
    if not default:
        raise RuntimeError("cast sheet has no usable voice")
    return default, text


def run_file_pipeline(
    media: Path,
    subs: Path,
    cast_path: Path,
    out_dir: Path,
    *,
    max_workers: int = 4,
    limit_lines: int | None = None,
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

    cast = load_cast_sheet(cast_path)
    captions = load_captions(subs)
    if limit_lines is not None:
        captions = captions[:limit_lines]
    if not captions:
        raise RuntimeError("no caption lines after filtering")

    work = out_dir / "work"
    cache_root = out_dir / "render_cache"
    work.mkdir(exist_ok=True)

    full_wav = extract_wav(media, work / "full.wav")
    me = resolve_me_stem(full_wav, work)
    me_wav = me.path
    emit("me_stem_ready", method=me.method, path=str(me_wav))

    model = elevenlabs_tts_model()
    clips: list[TimedClip] = []
    manifest_lines: list[dict] = []

    def render_one(cap_index: int) -> tuple[TimedClip, dict, bool]:
        cap = captions[cap_index]
        binding, script = _resolve_binding(cap.text, cast)
        script = normalize_script_text(script)
        if not binding.voice_id:
            raise ElevenLabsError(f"no voice_id for character {binding.character_id}")

        slice_path = work / f"slice_{cap.index:04d}.wav"
        slice_wav(full_wav, slice_path, cap.start_s, min(cap.end_s, cap.start_s + 2.5))
        bucket = emotion_bucket_from_wav(slice_path)
        key = cache_key(binding.voice_id, script, bucket, model)
        out_mp3 = cache_path(cache_root, key)
        hit = out_mp3.is_file()
        if hit:
            emit("cache_hit", character_id=binding.character_id, key=key)
        else:
            tts_to_file(
                script,
                binding.voice_id,
                out_mp3,
                model_id=model,
                style=style_for_bucket(bucket),
            )
            emit(
                "line_rendered",
                character_id=binding.character_id,
                index=cap.index,
                chars=len(script),
                emotion=bucket,
            )
        emit(
            "cast_matched",
            character_id=binding.character_id,
            index=cap.index,
            confidence=1.0 if _SPEAKER_PREFIX.match(cap.text) else 0.5,
        )
        meta = {
            "index": cap.index,
            "start_s": cap.start_s,
            "end_s": cap.end_s,
            "text": script,
            "source_caption": cap.text,
            "character_id": binding.character_id,
            "voice_id": binding.voice_id,
            "emotion": bucket,
            "cache_hit": hit,
            "audio": str(out_mp3),
        }
        return (
            TimedClip(
                start_s=cap.start_s,
                path=out_mp3,
                text=script,
                character_id=binding.character_id,
            ),
            meta,
            hit,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = [pool.submit(render_one, i) for i in range(len(captions))]
        for fut in as_completed(futs):
            clip, meta, _hit = fut.result()
            clips.append(clip)
            manifest_lines.append(meta)

    clips.sort(key=lambda c: c.start_s)
    manifest_lines.sort(key=lambda m: m["index"])

    mixed_wav = mix_to_wav(me_wav, clips, work / "mixed.wav")
    out_mka = wav_to_mka(mixed_wav, out_dir / f"{media.stem}.autodub.mka")
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
    return {
        "mka": str(out_mka),
        "manifest": str(manifest_path),
        "lines": len(manifest_lines),
        "me_method": me.method,
    }
