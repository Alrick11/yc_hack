"""Append-only, privacy-safe event stream for recording and replay."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class JsonlEventLog:
    def __init__(self, path: str | Path, session_id: str):
        self.path = Path(path)
        self.session_id = session_id
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event_type: str, **payload: Any) -> None:
        event = {"session_id": self.session_id, "ts": time.time(), "type": event_type, **payload}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")


def read_events(path: str | Path) -> list[dict[str, Any]]:
    events = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events

