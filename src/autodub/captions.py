"""Parse EN captions — caption text is the script (no invention)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pysubs2


@dataclass(frozen=True)
class CaptionLine:
    index: int
    start_s: float
    end_s: float
    text: str
    style: str = ""


_SKIP_STYLE_HINTS = ("op", "ed", "sign", "song", "karaoke", "title")


def _clean_text(raw: str) -> str:
    # pysubs2 already strips some overrides; normalize whitespace
    text = " ".join(raw.replace("\n", " ").split())
    return text.strip()


def load_captions(path: Path | str) -> list[CaptionLine]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"captions not found: {path}")
    subs = pysubs2.load(str(path))
    lines: list[CaptionLine] = []
    idx = 0
    for event in subs:
        if event.is_comment:
            continue
        style = (event.style or "").strip()
        style_l = style.lower()
        if any(h in style_l for h in _SKIP_STYLE_HINTS):
            continue
        text = _clean_text(event.plaintext)
        if not text:
            continue
        start_s = event.start / 1000.0
        end_s = event.end / 1000.0
        if end_s <= start_s:
            continue
        lines.append(
            CaptionLine(index=idx, start_s=start_s, end_s=end_s, text=text, style=style)
        )
        idx += 1
    return lines


def normalize_script_text(text: str) -> str:
    return " ".join(text.split())
