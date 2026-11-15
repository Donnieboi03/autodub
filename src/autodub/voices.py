"""Voice bank helpers: IVC from ref wavs + operator cast sheet writer."""

from __future__ import annotations

from pathlib import Path

from autodub.cast_sheet import write_cast_sheet
from autodub.elevenlabs_client import create_instant_voice_clone, list_voices
from autodub.events import emit
from autodub.separate import extract_wav, slice_wav


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
    emit("voice_cloned", name=name, voice_id=voice_id, ref=str(ref))
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
        "note": "Stock voices bootstrap. Replace voice_id via autodub voices ivc when dub refs exist.",
    }
    return write_cast_sheet(out_path, payload)
