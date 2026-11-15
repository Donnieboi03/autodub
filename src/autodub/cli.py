"""CLI: doctor / run / voices / fixture."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from autodub.config import elevenlabs_key_present, elevenlabs_tts_model, load_env


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
    print(f"info: TTS model = {elevenlabs_tts_model()}")
    return 0 if ok else 1


def _cmd_fixture(args: argparse.Namespace) -> int:
    from autodub.fixtures import build_synthetic_episode

    out = Path(args.out)
    paths = build_synthetic_episode(out, duration_s=float(args.duration))
    print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from autodub.pipeline import run_file_pipeline

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

    result = run_file_pipeline(
        media,
        subs,
        cast,
        Path(args.out),
        max_workers=int(args.workers),
        limit_lines=args.limit_lines,
    )
    print(json.dumps(result, indent=2))
    return 0


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
    p_run.set_defaults(func=_cmd_run)

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

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    load_env()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
