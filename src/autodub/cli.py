"""CLI entry (scaffold)."""

from __future__ import annotations

import argparse
import sys

from autodub.config import load_env, elevenlabs_key_present


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autodub", description="AutoDub scaffold")
    parser.add_argument(
        "command",
        nargs="?",
        default="doctor",
        choices=["doctor"],
        help="doctor — check .env / key presence",
    )
    args = parser.parse_args(argv)

    load_env()

    if args.command == "doctor":
        if elevenlabs_key_present():
            print("ok: ELEVENLABS_API_KEY is set")
            return 0
        print(
            "missing: ELEVENLABS_API_KEY\n"
            "  cp .env.example .env\n"
            "  # paste your key into .env",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
