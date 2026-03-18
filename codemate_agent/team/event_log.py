"""
Structured JSONL event logger for team runtime.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


class StructuredEventLogger:
    """Write structured events to a JSONL file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, event: str, payload: dict[str, Any] | None = None) -> None:
        record = {
            "ts": time.time(),
            "event": event,
            "payload": payload or {},
        }
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
