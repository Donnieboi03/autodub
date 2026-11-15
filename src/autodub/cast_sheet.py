"""Cast sheet load/save — real sheets live under operator/cast/."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class VoiceBinding:
    character_id: str
    name: str
    backend: str
    voice_id: str | None
    ref_wav: str | None = None


@dataclass
class CastSheet:
    path: Path
    schema_version: int
    show_title: str
    season: int
    bindings: list[VoiceBinding]

    def by_character_id(self) -> dict[str, VoiceBinding]:
        return {b.character_id: b for b in self.bindings}

    def default_voice(self) -> VoiceBinding | None:
        for b in self.bindings:
            if b.character_id != "_guest":
                return b
        return self.bindings[0] if self.bindings else None


def load_cast_sheet(path: Path | str) -> CastSheet:
    path = Path(path)
    data = json.loads(path.read_text())
    show = data.get("show") or {}
    bindings: list[VoiceBinding] = []
    for raw in data.get("bindings") or []:
        voice = raw.get("voice") or {}
        bindings.append(
            VoiceBinding(
                character_id=str(raw["character_id"]),
                name=str(raw.get("name") or raw["character_id"]),
                backend=str(voice.get("backend") or "elevenlabs"),
                voice_id=voice.get("voice_id"),
                ref_wav=voice.get("ref_wav"),
            )
        )
    if not bindings:
        raise ValueError(f"cast sheet has no bindings: {path}")
    return CastSheet(
        path=path,
        schema_version=int(data.get("schema_version") or 1),
        show_title=str(show.get("title") or "unknown"),
        season=int(show.get("season") or 1),
        bindings=bindings,
    )


def write_cast_sheet(path: Path | str, payload: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path
