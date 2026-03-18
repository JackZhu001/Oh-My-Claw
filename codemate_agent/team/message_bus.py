"""
JSONL inbox based message bus.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Iterable

from .protocols import TeamMessage, VALID_MESSAGE_TYPES


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class MessageBus:
    """Append-only message bus with one inbox file per member."""

    def __init__(self, inbox_dir: Path):
        self.dir = Path(inbox_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _normalize_name(self, name: str) -> str:
        normalized = (name or "").strip()
        if not normalized or not _SAFE_NAME_RE.match(normalized):
            raise ValueError(f"invalid inbox name: {name}")
        return normalized

    def _inbox_path(self, name: str) -> Path:
        safe_name = self._normalize_name(name)
        return self.dir / f"{safe_name}.jsonl"

    def send(
        self,
        sender: str,
        to: str,
        content: str,
        msg_type: str = "message",
        extra: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if msg_type not in VALID_MESSAGE_TYPES:
            raise ValueError(f"invalid msg_type: {msg_type}")
        message = TeamMessage(
            msg_type=msg_type,
            sender=self._normalize_name(sender),
            content=content or "",
            request_id=request_id,
            extra=dict(extra or {}),
        ).to_dict()
        inbox_path = self._inbox_path(to)
        with self._lock:
            with open(inbox_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")
        return message

    def read_inbox(self, name: str, drain: bool = True) -> list[dict[str, Any]]:
        inbox_path = self._inbox_path(name)
        if not inbox_path.exists():
            return []
        with self._lock:
            raw = inbox_path.read_text(encoding="utf-8")
            if drain:
                inbox_path.write_text("", encoding="utf-8")

        messages: list[dict[str, Any]] = []
        for line in raw.splitlines():
            payload = line.strip()
            if not payload:
                continue
            try:
                messages.append(json.loads(payload))
            except json.JSONDecodeError:
                continue
        return messages

    def inbox_size(self, name: str) -> int:
        return len(self.read_inbox(name, drain=False))

    def broadcast(
        self,
        sender: str,
        content: str,
        teammates: Iterable[str],
        msg_type: str = "broadcast",
        extra: dict[str, Any] | None = None,
    ) -> int:
        count = 0
        for teammate in teammates:
            if teammate == sender:
                continue
            self.send(sender, teammate, content, msg_type=msg_type, extra=extra)
            count += 1
        return count
