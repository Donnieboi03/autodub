"""Structured pipeline events (contract-required)."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def emit(name: str, **payload: Any) -> Event:
    event = Event(name=name, payload=payload)
    print(json.dumps({"event": event.name, "ts": event.ts, **event.payload}), file=sys.stderr)
    return event
