"""ElevenLabs TTS + Instant Voice Clone (API)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from autodub.config import elevenlabs_tts_model, load_env

API = "https://api.elevenlabs.io/v1"


class ElevenLabsError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    load_env()
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise ElevenLabsError("ELEVENLABS_API_KEY not set")
    return {"xi-api-key": key}


def list_voices() -> list[dict]:
    with httpx.Client(timeout=60.0) as client:
        r = client.get(f"{API}/voices", headers=_headers())
        if r.status_code >= 400:
            raise ElevenLabsError(f"list_voices {r.status_code}: {r.text[:200]}")
        return list(r.json().get("voices") or [])


def tts_to_file(
    text: str,
    voice_id: str,
    out_path: Path,
    *,
    model_id: str | None = None,
    stability: float = 0.4,
    similarity_boost: float = 0.75,
    style: float = 0.35,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    model = model_id or elevenlabs_tts_model()
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": True,
        },
    }
    url = f"{API}/text-to-speech/{voice_id}"
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            url,
            headers={**_headers(), "Accept": "audio/mpeg", "Content-Type": "application/json"},
            content=json.dumps(payload),
        )
        if r.status_code >= 400:
            raise ElevenLabsError(f"tts {r.status_code}: {r.text[:300]}")
        out_path.write_bytes(r.content)
    return out_path


def create_instant_voice_clone(name: str, audio_paths: list[Path], description: str = "") -> str:
    """Create IVC; returns voice_id. Consumes account voice slot."""
    files = []
    handles = []
    try:
        for p in audio_paths:
            p = Path(p)
            if not p.is_file():
                raise ElevenLabsError(f"ref audio missing: {p}")
            fh = p.open("rb")
            handles.append(fh)
            files.append(("files", (p.name, fh, "application/octet-stream")))
        data = {"name": name}
        if description:
            data["description"] = description
        with httpx.Client(timeout=180.0) as client:
            r = client.post(
                f"{API}/voices/add",
                headers=_headers(),
                data=data,
                files=files,
            )
            if r.status_code >= 400:
                raise ElevenLabsError(f"ivc {r.status_code}: {r.text[:400]}")
            voice_id = r.json().get("voice_id")
            if not voice_id:
                raise ElevenLabsError(f"ivc missing voice_id: {r.text[:200]}")
            return str(voice_id)
    finally:
        for fh in handles:
            fh.close()
