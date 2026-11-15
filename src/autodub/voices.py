"""Voice bank helpers: IVC from ref wavs + operator cast sheet writer.

IVC enrollment is gated by caption evidence (CONTRACT dual-source + IVC policy):
the slice window must overlap speaker-labeled EN cues matching ``character_id``.
"""

from __future__ import annotations

import re
from pathlib import Path

from autodub.captions import CaptionLine, load_captions
from autodub.cast_sheet import write_cast_sheet
from autodub.elevenlabs_client import create_instant_voice_clone, list_voices
from autodub.events import emit
from autodub.separate import extract_wav, slice_wav

_SPEAKER_PREFIX = re.compile(r"^([A-Za-z][A-Za-z0-9 _'-]{0,40}):\s+(.*)$")


class CaptionVerifyError(ValueError):
    """IVC enrollment slice failed caption speaker verification."""


def character_id_from_name(name: str) -> str:
    """Map a display / IVC name to a ``character_id`` slug."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _normalize_speaker_token(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")


def speaker_labels_for_line(line: CaptionLine) -> set[str]:
    """Speaker tokens from ASS style and/or ``Name:`` text prefix."""
    labels: set[str] = set()
    if line.style:
        labels.add(_normalize_speaker_token(line.style))
    m = _SPEAKER_PREFIX.match(line.text)
    if m:
        labels.add(_normalize_speaker_token(m.group(1)))
    return {lab for lab in labels if lab}


def overlapping_caption_lines(
    captions: list[CaptionLine],
    start_s: float,
    end_s: float,
) -> list[CaptionLine]:
    if end_s <= start_s:
        raise CaptionVerifyError(
            "caption-verify failed: enrollment window end must be greater than start"
        )
    return [
        line
        for line in captions
        if line.start_s < end_s and line.end_s > start_s
    ]


def verify_ivc_caption_window(
    captions: list[CaptionLine] | Path | str,
    *,
    character_id: str,
    start_s: float,
    end_s: float,
) -> list[CaptionLine]:
    """Assert ``[start_s, end_s]`` overlaps cue(s) labeled as ``character_id``.

    Raises ``CaptionVerifyError`` with a ``caption-verify failed`` message when
    captions are missing, the window has no cues, cues lack speaker labels, or
    no label matches the character.
    """
    if isinstance(captions, (str, Path)):
        path = Path(captions)
        if not path.is_file():
            raise CaptionVerifyError(
                f"caption-verify failed: subs not found: {path}"
            )
        captions = load_captions(path)

    cid = _normalize_speaker_token(character_id)
    if not cid:
        raise CaptionVerifyError(
            "caption-verify failed: character_id is empty"
        )

    overlap = overlapping_caption_lines(captions, start_s, end_s)
    if not overlap:
        raise CaptionVerifyError(
            f"caption-verify failed: no caption cues overlap [{start_s}, {end_s}] "
            f"for character_id={cid!r}"
        )

    labeled = [(line, speaker_labels_for_line(line)) for line in overlap]
    if not any(labels for _, labels in labeled):
        raise CaptionVerifyError(
            f"caption-verify failed: overlapping cues in [{start_s}, {end_s}] "
            f"have no speaker prefix/style for character_id={cid!r}"
        )

    matched = [line for line, labels in labeled if cid in labels]
    if not matched:
        seen = sorted({lab for _, labels in labeled for lab in labels})
        raise CaptionVerifyError(
            f"caption-verify failed: no overlapping cue labeled {cid!r} "
            f"in [{start_s}, {end_s}] (saw labels: {seen})"
        )
    return matched


def create_ivc_from_media(
    name: str,
    media: Path,
    *,
    start_s: float,
    end_s: float,
    work_dir: Path,
    description: str = "",
) -> str:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    full = extract_wav(Path(media), work_dir / f"{name}_full.wav")
    ref = slice_wav(full, work_dir / f"{name}_ref.wav", start_s, end_s)
    voice_id = create_instant_voice_clone(name, [ref], description=description or f"AutoDub {name}")
    emit("voice_cloned", voice_name=name, voice_id=voice_id, ref=str(ref))
    return voice_id


def pick_stock_voices(n: int = 5) -> list[dict]:
    voices = list_voices()
    # prefer non-cloned premades for house fallback
    premades = [v for v in voices if (v.get("category") or "") in ("premade", "generated", "")]
    if len(premades) < n:
        premades = voices
    return premades[:n]


def write_operator_cast_from_stock(
    out_path: Path,
    *,
    show_title: str = "One Piece",
    season: int = 1,
) -> Path:
    """Bootstrap cast using account stock voices until dub-ref IVCs exist."""
    stock = pick_stock_voices(5)
    names = [
        ("luffy", "Luffy"),
        ("zoro", "Zoro"),
        ("nami", "Nami"),
        ("sanji", "Sanji"),
        ("narrator", "Narrator"),
    ]
    bindings = []
    for i, (cid, name) in enumerate(names):
        v = stock[i % len(stock)]
        bindings.append(
            {
                "character_id": cid,
                "name": name,
                "voice": {
                    "backend": "elevenlabs",
                    "voice_id": v.get("voice_id"),
                    "ref_wav": None,
                    "stock_name": v.get("name"),
                },
            }
        )
    payload = {
        "schema_version": 1,
        "show": {"title": show_title, "anilist_id": None, "season": season},
        "bindings": bindings,
        "note": (
            "Stock voices bootstrap. Replace voice_id via autodub voices ivc "
            "only with caption-verified EN refs (CONTRACT IVC policy)."
        ),
    }
    return write_cast_sheet(out_path, payload)
