"""
Team protocol models and request trackers.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


VALID_MESSAGE_TYPES = frozenset(
    {
        "message",
        "broadcast",
        "shutdown_request",
        "shutdown_response",
        "plan_approval_request",
        "plan_approval_response",
        "delegate_request",
        "delegate_accept",
        "delegate_reject",
        "artifact_submit",
        "review_request",
        "review_response",
        "handoff_request",
        "cancel_request",
        "status_report",
    }
)

_VALID_PROTOCOLS = frozenset(
    {
        "shutdown",
        "plan_approval",
        "delegate",
        "artifact",
        "review",
        "handoff",
        "cancel",
        "status",
    }
)
_VALID_REQUEST_STATUSES = frozenset(
    {"pending", "approved", "rejected", "cancelled", "completed", "failed"}
)


@dataclass
class TeamMessage:
    """Canonical team message."""

    msg_type: str
    sender: str
    content: str
    timestamp: float = field(default_factory=time.time)
    request_id: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "type": self.msg_type,
            "from": self.sender,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.request_id:
            payload["request_id"] = self.request_id
        if self.extra:
            payload.update(self.extra)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TeamMessage":
        data = dict(payload or {})
        msg_type = str(data.pop("type", "message"))
        sender = str(data.pop("from", ""))
        content = str(data.pop("content", ""))
        timestamp = float(data.pop("timestamp", time.time()))
        request_id = data.pop("request_id", None)
        if request_id is not None:
            request_id = str(request_id)
        return cls(
            msg_type=msg_type,
            sender=sender,
            content=content,
            timestamp=timestamp,
            request_id=request_id,
            extra=data,
        )


@dataclass
class RequestRecord:
    """Protocol request lifecycle record."""

    request_id: str
    protocol: str
    sender: str
    target: str
    status: str = "pending"
    reason: str = ""
    responder: str = ""
    task_id: Optional[int] = None
    session_id: str = ""
    parent_request_id: str = ""
    correlation_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "protocol": self.protocol,
            "sender": self.sender,
            "target": self.target,
            "status": self.status,
            "reason": self.reason,
            "responder": self.responder,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "parent_request_id": self.parent_request_id,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class RequestTracker:
    """Thread-safe tracker for protocol request state transitions."""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: dict[str, dict[str, RequestRecord]] = {
            protocol: {} for protocol in _VALID_PROTOCOLS
        }

    def _validate_protocol(self, protocol: str) -> str:
        normalized = (protocol or "").strip().lower()
        if normalized not in _VALID_PROTOCOLS:
            raise ValueError(f"unsupported protocol: {protocol}")
        return normalized

    def _validate_status(self, status: str) -> str:
        normalized = (status or "").strip().lower()
        if normalized not in _VALID_REQUEST_STATUSES:
            raise ValueError(f"unsupported status: {status}")
        return normalized

    def create_request(
        self,
        protocol: str,
        sender: str,
        target: str = "",
        payload: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
        task_id: Optional[int] = None,
        session_id: str = "",
        parent_request_id: str = "",
        correlation_id: str = "",
    ) -> RequestRecord:
        protocol_name = self._validate_protocol(protocol)
        rid = request_id or uuid.uuid4().hex[:8]
        now = time.time()
        record = RequestRecord(
            request_id=rid,
            protocol=protocol_name,
            sender=sender,
            target=target,
            status="pending",
            task_id=task_id,
            session_id=session_id,
            parent_request_id=parent_request_id,
            correlation_id=correlation_id,
            payload=dict(payload or {}),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._records[protocol_name][rid] = record
        return record

    def update_request(
        self,
        protocol: str,
        request_id: str,
        status: str,
        *,
        responder: str = "",
        reason: str = "",
        payload: Optional[dict[str, Any]] = None,
        create_if_missing: bool = False,
        sender: str = "",
        target: str = "",
        task_id: Optional[int] = None,
        session_id: str = "",
        parent_request_id: str = "",
        correlation_id: str = "",
    ) -> Optional[RequestRecord]:
        protocol_name = self._validate_protocol(protocol)
        status_name = self._validate_status(status)
        now = time.time()
        with self._lock:
            record = self._records[protocol_name].get(request_id)
            if record is None and create_if_missing:
                record = RequestRecord(
                    request_id=request_id,
                    protocol=protocol_name,
                    sender=sender,
                    target=target,
                    status="pending",
                    task_id=task_id,
                    session_id=session_id,
                    parent_request_id=parent_request_id,
                    correlation_id=correlation_id,
                    created_at=now,
                    updated_at=now,
                )
                self._records[protocol_name][request_id] = record
            if record is None:
                return None
            record.status = status_name
            record.updated_at = now
            if responder:
                record.responder = responder
            if reason:
                record.reason = reason
            if payload:
                merged = dict(record.payload)
                merged.update(payload)
                record.payload = merged
            if task_id is not None:
                record.task_id = task_id
            if session_id:
                record.session_id = session_id
            if parent_request_id:
                record.parent_request_id = parent_request_id
            if correlation_id:
                record.correlation_id = correlation_id
            return record

    def ingest_message(self, payload: dict[str, Any]) -> Optional[RequestRecord]:
        msg = TeamMessage.from_dict(payload)
        request_id = msg.request_id or str(msg.extra.get("request_id", "")).strip()
        if not request_id:
            return None

        if msg.msg_type == "shutdown_request":
            return self.create_request(
                "shutdown",
                sender=msg.sender,
                target=str(msg.extra.get("to", "")),
                payload=msg.extra,
                request_id=request_id,
            )

        if msg.msg_type == "shutdown_response":
            approved = bool(msg.extra.get("approve", False))
            status = "approved" if approved else "rejected"
            return self.update_request(
                "shutdown",
                request_id=request_id,
                status=status,
                responder=msg.sender,
                reason=msg.content or str(msg.extra.get("reason", "")),
                payload=msg.extra,
                create_if_missing=True,
            )

        if msg.msg_type == "plan_approval_request":
            return self.create_request(
                "plan_approval",
                sender=msg.sender,
                target=str(msg.extra.get("to", "")),
                payload=msg.extra,
                request_id=request_id,
            )

        if msg.msg_type == "plan_approval_response":
            approve_value = msg.extra.get("approve")
            if approve_value is None:
                status = "pending"
            else:
                status = "approved" if bool(approve_value) else "rejected"
            return self.update_request(
                "plan_approval",
                request_id=request_id,
                status=status,
                responder=msg.sender,
                reason=msg.content or str(msg.extra.get("feedback", "")),
                payload=msg.extra,
                create_if_missing=True,
            )

        if msg.msg_type == "delegate_request":
            return self.create_request(
                "delegate",
                sender=msg.sender,
                target=str(msg.extra.get("to", "")),
                payload=msg.extra,
                request_id=request_id,
                task_id=msg.extra.get("task_id"),
                session_id=str(msg.extra.get("session_id", "")),
                parent_request_id=str(msg.extra.get("parent_request_id", "")),
                correlation_id=str(msg.extra.get("correlation_id", "")),
            )

        if msg.msg_type in {"delegate_accept", "delegate_reject"}:
            status = "approved" if msg.msg_type == "delegate_accept" else "rejected"
            return self.update_request(
                "delegate",
                request_id=request_id,
                status=status,
                responder=msg.sender,
                reason=msg.content,
                payload=msg.extra,
                create_if_missing=True,
                task_id=msg.extra.get("task_id"),
                session_id=str(msg.extra.get("session_id", "")),
                parent_request_id=str(msg.extra.get("parent_request_id", "")),
                correlation_id=str(msg.extra.get("correlation_id", "")),
            )

        if msg.msg_type == "artifact_submit":
            return self.update_request(
                "artifact",
                request_id=request_id,
                status="completed",
                responder=msg.sender,
                reason=msg.content,
                payload=msg.extra,
                create_if_missing=True,
                task_id=msg.extra.get("task_id"),
                session_id=str(msg.extra.get("session_id", "")),
                parent_request_id=str(msg.extra.get("parent_request_id", "")),
                correlation_id=str(msg.extra.get("correlation_id", "")),
            )

        if msg.msg_type == "review_request":
            return self.create_request(
                "review",
                sender=msg.sender,
                target=str(msg.extra.get("to", "")),
                payload=msg.extra,
                request_id=request_id,
                task_id=msg.extra.get("task_id"),
                session_id=str(msg.extra.get("session_id", "")),
                parent_request_id=str(msg.extra.get("parent_request_id", "")),
                correlation_id=str(msg.extra.get("correlation_id", "")),
            )

        if msg.msg_type == "review_response":
            review_status = msg.extra.get("status", "completed")
            status = "approved" if str(review_status).lower() in {"approved", "pass", "completed"} else "rejected"
            return self.update_request(
                "review",
                request_id=request_id,
                status=status,
                responder=msg.sender,
                reason=msg.content or str(msg.extra.get("feedback", "")),
                payload=msg.extra,
                create_if_missing=True,
                task_id=msg.extra.get("task_id"),
                session_id=str(msg.extra.get("session_id", "")),
                parent_request_id=str(msg.extra.get("parent_request_id", "")),
                correlation_id=str(msg.extra.get("correlation_id", "")),
            )

        if msg.msg_type == "handoff_request":
            return self.create_request(
                "handoff",
                sender=msg.sender,
                target=str(msg.extra.get("to", "")),
                payload=msg.extra,
                request_id=request_id,
                task_id=msg.extra.get("task_id"),
                session_id=str(msg.extra.get("session_id", "")),
                parent_request_id=str(msg.extra.get("parent_request_id", "")),
                correlation_id=str(msg.extra.get("correlation_id", "")),
            )

        if msg.msg_type == "cancel_request":
            return self.update_request(
                "cancel",
                request_id=request_id,
                status="cancelled",
                responder=msg.sender,
                reason=msg.content or str(msg.extra.get("reason", "")),
                payload=msg.extra,
                create_if_missing=True,
                task_id=msg.extra.get("task_id"),
                session_id=str(msg.extra.get("session_id", "")),
                parent_request_id=str(msg.extra.get("parent_request_id", "")),
                correlation_id=str(msg.extra.get("correlation_id", "")),
            )

        if msg.msg_type == "status_report":
            return self.update_request(
                "status",
                request_id=request_id,
                status="pending",
                responder=msg.sender,
                reason=msg.content,
                payload=msg.extra,
                create_if_missing=True,
                task_id=msg.extra.get("task_id"),
                session_id=str(msg.extra.get("session_id", "")),
                parent_request_id=str(msg.extra.get("parent_request_id", "")),
                correlation_id=str(msg.extra.get("correlation_id", "")),
            )

        return None

    def get_request(self, protocol: str, request_id: str) -> Optional[dict[str, Any]]:
        protocol_name = self._validate_protocol(protocol)
        with self._lock:
            record = self._records[protocol_name].get(request_id)
            return record.to_dict() if record else None

    def pending_requests(self, protocol: Optional[str] = None) -> list[dict[str, Any]]:
        with self._lock:
            if protocol:
                protocol_name = self._validate_protocol(protocol)
                records = self._records[protocol_name].values()
            else:
                records = [
                    record
                    for per_protocol in self._records.values()
                    for record in per_protocol.values()
                ]
            return [r.to_dict() for r in records if r.status == "pending"]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts = {}
            pending = {}
            for protocol, records in self._records.items():
                values = list(records.values())
                counts[protocol] = {
                    "total": len(values),
                    "pending": sum(1 for r in values if r.status == "pending"),
                    "approved": sum(1 for r in values if r.status == "approved"),
                    "rejected": sum(1 for r in values if r.status == "rejected"),
                    "completed": sum(1 for r in values if r.status == "completed"),
                    "cancelled": sum(1 for r in values if r.status == "cancelled"),
                    "failed": sum(1 for r in values if r.status == "failed"),
                }
                pending[protocol] = [r.to_dict() for r in values if r.status == "pending"]
            return {"counts": counts, "pending": pending}

    def clear(self) -> None:
        with self._lock:
            for protocol in self._records:
                self._records[protocol].clear()
