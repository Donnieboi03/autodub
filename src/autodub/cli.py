"""CLI: doctor / run / watch / voices / fixture / score-voice."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from autodub.config import elevenlabs_key_present, elevenlabs_tts_model, load_env


def _apply_model_override(args: argparse.Namespace) -> None:
    """Optional --model sets AUTODUB_TTS_MODEL for this process (does not bake into .env)."""
    model = getattr(args, "model", None)
    if model:
        os.environ["AUTODUB_TTS_MODEL"] = str(model).strip()


def _cmd_doctor(_: argparse.Namespace) -> int:
    load_env()
    ok = True
    if elevenlabs_key_present():
        print("ok: ELEVENLABS_API_KEY is set")
    else:
        ok = False
        print(
            "missing: ELEVENLABS_API_KEY\n"
            "  cp .env.example .env\n"
            "  # paste your key into .env",
            file=sys.stderr,
        )
    if shutil.which("ffmpeg"):
        print("ok: ffmpeg on PATH")
    else:
        ok = False
        print("missing: ffmpeg (required for extract/mix/mka)", file=sys.stderr)
    from autodub.separate import separator_status

    sep = separator_status()
    if sep["demucs"]:
        print("ok: demucs available (preferred M&E)")
    else:
        print("info: demucs not installed — pip install 'autodub[separate]' (or demucs)")
    if sep["audio_separator"]:
        print("ok: audio-separator available (UVR/MelBand fallback)")
    else:
        print(
            "info: audio-separator optional — "
            "pip install 'audio-separator[cpu]' (large models; not in default deps)"
        )
    print(f"info: M&E order = {sep['default_me_order']}")
    print(f"info: TTS model = {elevenlabs_tts_model()}")
    return 0 if ok else 1


def _cmd_fixture(args: argparse.Namespace) -> int:
    from autodub.fixtures import build_synthetic_episode

    out = Path(args.out)
    paths = build_synthetic_episode(out, duration_s=float(args.duration))
    print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2))
    return 0


def _require_run_paths(args: argparse.Namespace) -> tuple[Path, Path, Path] | int:
    media = Path(args.media)
    subs = Path(args.subs)
    cast = Path(args.cast)
    if not media.is_file():
        print(f"fail: media not found: {media}", file=sys.stderr)
        return 2
    if not subs.is_file():
        print(f"fail: subs not found: {subs}", file=sys.stderr)
        return 2
    if not cast.is_file():
        print(f"fail: cast sheet not found: {cast}", file=sys.stderr)
        return 2
    return media, subs, cast


def _cmd_run(args: argparse.Namespace) -> int:
    from autodub.pipeline import run_file_pipeline

    _apply_model_override(args)
    paths = _require_run_paths(args)
    if isinstance(paths, int):
        return paths
    media, subs, cast = paths

    result = run_file_pipeline(
        media,
        subs,
        cast,
        Path(args.out),
        max_workers=int(args.workers),
        limit_lines=args.limit_lines,
        allow_caption_trim=bool(args.allow_caption_trim),
    )
    print(json.dumps(result, indent=2))
    return 0


def _cmd_score_voice(args: argparse.Namespace) -> int:
    from autodub.score_voice import ScoreVoiceError, score_similarity

    ref = Path(args.ref)
    hyp = Path(args.hyp)
    if not ref.is_file():
        print(f"fail: ref not found: {ref}", file=sys.stderr)
        return 2
    if not hyp.is_file():
        print(f"fail: hyp not found: {hyp}", file=sys.stderr)
        return 2
    try:
        sim = score_similarity(ref, hyp)
    except ScoreVoiceError as exc:
        print(f"fail: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"ref": str(ref), "hyp": str(hyp), "spk_sim": sim}, indent=2))
    return 0


def build_watch_player_argv(
    media: Path,
    mka: Path,
    *,
    out_dir: Path,
    player_path: str | None = None,
    ffmpeg_path: str | None = None,
) -> list[str]:
    """Build argv to play ``media`` video with external EN audio from ``mka``.

    Prefer mpv ``--audio-file``. ffplay cannot take dual ``-i``; remux to a
    short-lived temp mp4 under ``out_dir`` then play that.
    """
    player = player_path or shutil.which("mpv") or shutil.which("ffplay")
    if not player:
        raise FileNotFoundError("need mpv or ffplay on PATH to watch")
    media = Path(media)
    mka = Path(mka)
    out_dir = Path(out_dir)
    if Path(player).name == "mpv":
        return [player, f"--audio-file={mka}", str(media)]

    ffmpeg = ffmpeg_path or shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffplay fallback needs ffmpeg to remux video+mka")
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_mp4 = out_dir / f"{media.stem}.autodub.watch.mp4"
    remux = [
        ffmpeg,
        "-y",
        "-i",
        str(media),
        "-i",
        str(mka),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(temp_mp4),
    ]
    subprocess.check_call(remux)
    return [player, "-autoexit", str(temp_mp4)]


def _cmd_watch(args: argparse.Namespace) -> int:
    """Run pipeline if mka missing/stale, then play video + EN track."""
    from autodub.pipeline import run_file_pipeline

    _apply_model_override(args)
    paths = _require_run_paths(args)
    if isinstance(paths, int):
        return paths
    media, subs, cast = paths
    out = Path(args.out)
    mka = out / f"{media.stem}.autodub.mka"
    need_run = args.force or (not mka.is_file())
    if mka.is_file() and not args.force:
        # stale if media or subs newer than mka
        if media.stat().st_mtime > mka.stat().st_mtime or subs.stat().st_mtime > mka.stat().st_mtime:
            need_run = True
    if need_run:
        result = run_file_pipeline(
            media,
            subs,
            cast,
            out,
            max_workers=int(args.workers),
            limit_lines=args.limit_lines,
            allow_caption_trim=bool(args.allow_caption_trim),
        )
        print(json.dumps(result, indent=2))
        mka = Path(result["mka"])
    else:
        print(json.dumps({"mka": str(mka), "skipped_run": True}, indent=2))

    try:
        cmd = build_watch_player_argv(media, mka, out_dir=out)
    except FileNotFoundError as exc:
        print(f"fail: {exc}", file=sys.stderr)
        return 2
    print(f"# playing: {' '.join(cmd)}", file=sys.stderr)
    return int(subprocess.call(cmd))


def _cmd_voices_list(_: argparse.Namespace) -> int:
    from autodub.elevenlabs_client import list_voices

    voices = list_voices()
    for v in voices:
        print(f"{v.get('voice_id')}\t{v.get('category')}\t{v.get('name')}")
    print(f"# {len(voices)} voices", file=sys.stderr)
    return 0


def _cmd_voices_stock_cast(args: argparse.Namespace) -> int:
    from autodub.voices import write_operator_cast_from_stock

    out = Path(args.out)
    path = write_operator_cast_from_stock(
        out,
        show_title=args.show_title,
        season=int(args.season),
    )
    print(f"wrote {path}")
    return 0


def _cmd_voices_ivc(args: argparse.Namespace) -> int:
    from autodub.voices import create_ivc_from_media

    media = Path(args.media)
    if not media.is_file():
        print(
            f"fail: media path missing for IVC (fill operator/DECISIONS.md): {media}",
            file=sys.stderr,
        )
        return 2
    voice_id = create_ivc_from_media(
        args.name,
        media,
        start_s=float(args.start),
        end_s=float(args.end),
        work_dir=Path(args.work),
        description=args.description or "",
    )
    print(json.dumps({"name": args.name, "voice_id": voice_id}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autodub", description="AutoDub")
    sub = parser.add_subparsers(dest="command")

    p_doc = sub.add_parser("doctor", help="check .env key + ffmpeg")
    p_doc.set_defaults(func=_cmd_doctor)

    p_fix = sub.add_parser("fixture", help="build synthetic episode media+srt")
    p_fix.add_argument("--out", required=True, help="output directory")
    p_fix.add_argument("--duration", default="12", help="seconds")
    p_fix.set_defaults(func=_cmd_fixture)

    p_run = sub.add_parser("run", help="file pipeline → .mka")
    p_run.add_argument("--media", required=True)
    p_run.add_argument("--subs", required=True)
    p_run.add_argument("--cast", required=True)
    p_run.add_argument("--out", required=True, help="run output directory")
    p_run.add_argument("--workers", default="2")
    p_run.add_argument(
        "--limit-lines",
        type=int,
        default=None,
        help="cap caption lines (save TTS credits)",
    )
    p_run.add_argument(
        "--allow-caption-trim",
        action="store_true",
        help="allow shortening caption text for timing fit only",
    )
    p_run.add_argument(
        "--model",
        default=None,
        help="TTS model override (sets AUTODUB_TTS_MODEL; default stays Flash via env)",
    )
    p_run.set_defaults(func=_cmd_run)

    p_watch = sub.add_parser("watch", help="run pipeline if needed, then play video+EN")
    p_watch.add_argument("--media", required=True)
    p_watch.add_argument("--subs", required=True)
    p_watch.add_argument("--cast", required=True)
    p_watch.add_argument("--out", required=True, help="run output directory")
    p_watch.add_argument("--workers", default="2")
    p_watch.add_argument("--limit-lines", type=int, default=None)
    p_watch.add_argument("--allow-caption-trim", action="store_true")
    p_watch.add_argument("--force", action="store_true", help="always re-run pipeline")
    p_watch.add_argument(
        "--model",
        default=None,
        help="TTS model override (sets AUTODUB_TTS_MODEL; default stays Flash via env)",
    )
    p_watch.set_defaults(func=_cmd_watch)

    p_voices = sub.add_parser("voices", help="voice bank helpers")
    vsub = p_voices.add_subparsers(dest="voices_cmd", required=True)

    p_vl = vsub.add_parser("list", help="list ElevenLabs voices")
    p_vl.set_defaults(func=_cmd_voices_list)

    p_vs = vsub.add_parser("stock-cast", help="write cast sheet from stock voices")
    p_vs.add_argument("--out", required=True)
    p_vs.add_argument("--show-title", default="One Piece")
    p_vs.add_argument("--season", default="1")
    p_vs.set_defaults(func=_cmd_voices_stock_cast)

    p_vi = vsub.add_parser("ivc", help="create IVC from media slice (needs real path)")
    p_vi.add_argument("--name", required=True)
    p_vi.add_argument("--media", required=True)
    p_vi.add_argument("--start", required=True, type=float)
    p_vi.add_argument("--end", required=True, type=float)
    p_vi.add_argument("--work", default="operator/ref_work")
    p_vi.add_argument("--description", default="")
    p_vi.set_defaults(func=_cmd_voices_ivc)

    p_score = sub.add_parser(
        "score-voice",
        help="cosine speaker similarity (SpeechBrain ECAPA soft gate)",
    )
    p_score.add_argument("--ref", required=True, help="reference wav")
    p_score.add_argument("--hyp", required=True, help="hypothesis / TTS wav")
    p_score.set_defaults(func=_cmd_score_voice)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    load_env()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
