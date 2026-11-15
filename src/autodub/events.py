"""Structured pipeline events (contract-required)."""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_jsonl_path: Path | None = None


@dataclass
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def set_events_sink(path: Path | None) -> None:
    """Append events to this JSONL path for the current run (or None to disable)."""
    global _jsonl_path
    with _lock:
        _jsonl_path = Path(path) if path else None
        if _jsonl_path is not None:
            _jsonl_path.parent.mkdir(parents=True, exist_ok=True)


def emit(name: str, **payload: Any) -> Event:
    event = Event(name=name, payload=payload)
    record = {"event": event.name, "ts": event.ts, **event.payload}
    line = json.dumps(record)
    print(line, file=sys.stderr)
    with _lock:
        sink = _jsonl_path
    if sink is not None:
        with _lock:
            with open(sink, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    return event
