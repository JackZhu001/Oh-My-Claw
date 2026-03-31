"""
File-based task board.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

VALID_TASK_STATUSES = frozenset(
    {
        "pending",
        "leased",
        "in_progress",
        "blocked",
        "review",
        "completed",
        "failed",
        "cancelled",
    }
)


class TaskBoard:
    """Task board backed by .tasks/task_*.json files."""

    def __init__(self, tasks_dir: Path):
        self.dir = Path(tasks_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _task_path(self, task_id: int) -> Path:
        return self.dir / f"task_{int(task_id)}.json"

    def _write_task(self, task: dict[str, Any]) -> None:
        path = self._task_path(int(task["id"]))
        path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_task(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _next_task_id(self) -> int:
        max_id = 0
        for path in self.dir.glob("task_*.json"):
            stem = path.stem
            suffix = stem.replace("task_", "", 1)
            if suffix.isdigit():
                max_id = max(max_id, int(suffix))
        return max_id + 1

    def create_task(
        self,
        subject: str,
        description: str = "",
        *,
        blocked_by: Optional[list[int]] = None,
        blocks: Optional[list[int]] = None,
        worktree: str = "",
        assignee: str = "",
        delegated_by: str = "",
        parent_task_id: Optional[int] = None,
        artifact_dir: str = "",
        priority: int = 3,
        max_attempts: int = 2,
        correlation_id: str = "",
        request_id: str = "",
        session_id: str = "",
    ) -> dict[str, Any]:
        clean_subject = (subject or "").strip()
        if not clean_subject:
            raise ValueError("task subject cannot be empty")

        now = time.time()
        with self._lock:
            task_id = self._next_task_id()
            task = {
                "id": task_id,
                "subject": clean_subject,
                "description": (description or "").strip(),
                "status": "pending",
                "owner": "",
                "assignee": (assignee or "").strip(),
                "delegated_by": (delegated_by or "").strip(),
                "parent_task_id": int(parent_task_id) if parent_task_id is not None else None,
                "artifact_dir": (artifact_dir or "").strip(),
                "blockedBy": list(blocked_by or []),
                "blocks": list(blocks or []),
                "worktree": (worktree or "").strip(),
                "priority": int(priority),
                "attempt": 0,
                "max_attempts": max(1, int(max_attempts)),
                "lease_owner": "",
                "lease_expires_at": 0.0,
                "failure_reason": "",
                "artifact_manifest": "",
                "correlation_id": (correlation_id or "").strip(),
                "request_id": (request_id or "").strip(),
                "session_id": (session_id or "").strip(),
                "created_at": now,
                "updated_at": now,
            }
            self._write_task(task)
            return dict(task)

    def _update_block_relationship(self, task_id: int, blocks: list[int]) -> None:
        for blocked_id in blocks:
            blocked_path = self._task_path(blocked_id)
            if not blocked_path.exists():
                continue
            blocked = self._read_task(blocked_path)
            blocked_by = list(blocked.get("blockedBy", []))
            if task_id not in blocked_by:
                blocked_by.append(task_id)
                blocked["blockedBy"] = blocked_by
                blocked["updated_at"] = time.time()
                self._write_task(blocked)

    def _clear_dependency(self, completed_id: int) -> None:
        for path in self.dir.glob("task_*.json"):
            task = self._read_task(path)
            blocked_by = list(task.get("blockedBy", []))
            if completed_id in blocked_by:
                task["blockedBy"] = [tid for tid in blocked_by if tid != completed_id]
                task["updated_at"] = time.time()
                self._write_task(task)

    def list_tasks(self) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        for path in sorted(self.dir.glob("task_*.json")):
            try:
                tasks.append(self._read_task(path))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"跳过损坏的任务文件 {path.name}: {e}")
                continue
        tasks.sort(key=lambda item: int(item.get("id", 0)))
        return tasks

    def get_task(self, task_id: int) -> Optional[dict[str, Any]]:
        path = self._task_path(task_id)
        if not path.exists():
            return None
        try:
            return self._read_task(path)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取任务文件失败 {path.name}: {e}")
            return None

    def scan_unclaimed_tasks(self) -> list[dict[str, Any]]:
        tasks = self.list_tasks()
        return [
            task
            for task in tasks
            if self._can_claim(task)
            and not task.get("blockedBy")
        ]

    def _lease_active(self, task: dict[str, Any]) -> bool:
        expires = float(task.get("lease_expires_at", 0.0) or 0.0)
        owner = str(task.get("lease_owner", "") or "").strip()
        return bool(owner) and expires > time.time()

    def _can_claim(self, task: dict[str, Any]) -> bool:
        status = str(task.get("status", "pending"))
        if status != "pending":
            return False
        if task.get("owner"):
            return False
        if self._lease_active(task):
            return False
        return True

    def claim_task(
        self, task_id: int, owner: str, *, lease_ttl_sec: int = 300
    ) -> Optional[dict[str, Any]]:
        clean_owner = (owner or "").strip()
        if not clean_owner:
            raise ValueError("owner cannot be empty")

        with self._lock:
            path = self._task_path(task_id)
            if not path.exists():
                return None
            task = self._read_task(path)
            if not self._can_claim(task) or task.get("blockedBy"):
                return None
            now = time.time()
            task["owner"] = clean_owner
            task["status"] = "in_progress"
            task["attempt"] = int(task.get("attempt", 0)) + 1
            task["lease_owner"] = clean_owner
            task["lease_expires_at"] = now + max(30, int(lease_ttl_sec))
            task["updated_at"] = now
            self._write_task(task)
            return dict(task)

    def _remove_deleted_dependencies(self, deleted_ids: set[int]) -> None:
        if not deleted_ids:
            return
        for path in self.dir.glob("task_*.json"):
            task = self._read_task(path)
            blocked = [tid for tid in task.get("blockedBy", []) if int(tid) not in deleted_ids]
            blocks = [tid for tid in task.get("blocks", []) if int(tid) not in deleted_ids]
            if blocked != task.get("blockedBy", []) or blocks != task.get("blocks", []):
                task["blockedBy"] = blocked
                task["blocks"] = blocks
                task["updated_at"] = time.time()
                self._write_task(task)

    def cleanup_tasks(self, subject_prefix: str = "", all_tasks: bool = False) -> list[int]:
        clean_prefix = (subject_prefix or "").strip()
        with self._lock:
            deleted_ids: list[int] = []
            for path in sorted(self.dir.glob("task_*.json")):
                task = self._read_task(path)
                subject = str(task.get("subject", ""))
                should_delete = all_tasks or (clean_prefix and subject.startswith(clean_prefix))
                if not should_delete:
                    continue
                task_id = int(task.get("id", 0))
                path.unlink(missing_ok=True)
                deleted_ids.append(task_id)

            self._remove_deleted_dependencies(set(deleted_ids))
            return deleted_ids

    def claim_first_unclaimed(self, owner: str) -> Optional[dict[str, Any]]:
        with self._lock:
            for path in sorted(self.dir.glob("task_*.json")):
                task = self._read_task(path)
                if self._can_claim(task) and not task.get("blockedBy"):
                    now = time.time()
                    task["owner"] = owner
                    task["status"] = "in_progress"
                    task["attempt"] = int(task.get("attempt", 0)) + 1
                    task["lease_owner"] = owner
                    task["lease_expires_at"] = now + 300
                    task["updated_at"] = now
                    self._write_task(task)
                    return dict(task)
        return None

    def renew_lease(
        self, task_id: int, owner: str, *, lease_ttl_sec: int = 300
    ) -> Optional[dict[str, Any]]:
        with self._lock:
            path = self._task_path(task_id)
            if not path.exists():
                return None
            task = self._read_task(path)
            if task.get("owner") != owner:
                return None
            task["lease_owner"] = owner
            task["lease_expires_at"] = time.time() + max(30, int(lease_ttl_sec))
            task["updated_at"] = time.time()
            self._write_task(task)
            return dict(task)

    def release_lease(
        self, task_id: int, owner: str, *, to_status: str = "pending"
    ) -> Optional[dict[str, Any]]:
        clean_status = str(to_status).strip().lower()
        if clean_status not in VALID_TASK_STATUSES:
            raise ValueError(f"invalid task status: {to_status}")
        with self._lock:
            path = self._task_path(task_id)
            if not path.exists():
                return None
            task = self._read_task(path)
            if owner and task.get("owner") and task.get("owner") != owner:
                return None
            task["status"] = clean_status
            task["owner"] = "" if clean_status == "pending" else task.get("owner", "")
            task["lease_owner"] = ""
            task["lease_expires_at"] = 0.0
            task["updated_at"] = time.time()
            self._write_task(task)
            return dict(task)

    def mark_failed(
        self,
        task_id: int,
        *,
        owner: str = "",
        reason: str = "",
        retryable: bool = False,
    ) -> Optional[dict[str, Any]]:
        with self._lock:
            path = self._task_path(task_id)
            if not path.exists():
                return None
            task = self._read_task(path)
            if owner and task.get("owner") and task.get("owner") != owner:
                return None
            attempts = int(task.get("attempt", 0))
            max_attempts = int(task.get("max_attempts", 1))
            if retryable and attempts < max_attempts:
                task["status"] = "pending"
                task["owner"] = ""
            else:
                task["status"] = "failed"
            task["failure_reason"] = str(reason or "").strip()
            task["lease_owner"] = ""
            task["lease_expires_at"] = 0.0
            task["updated_at"] = time.time()
            self._write_task(task)
            return dict(task)

    def update_task(
        self,
        task_id: int,
        *,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        add_blocked_by: Optional[list[int]] = None,
        add_blocks: Optional[list[int]] = None,
        assignee: Optional[str] = None,
        delegated_by: Optional[str] = None,
        parent_task_id: Optional[int] = None,
        artifact_dir: Optional[str] = None,
        priority: Optional[int] = None,
        max_attempts: Optional[int] = None,
        lease_owner: Optional[str] = None,
        lease_expires_at: Optional[float] = None,
        failure_reason: Optional[str] = None,
        artifact_manifest: Optional[str] = None,
        correlation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        with self._lock:
            path = self._task_path(task_id)
            if not path.exists():
                return None
            task = self._read_task(path)

            if owner is not None:
                task["owner"] = str(owner).strip()
            if assignee is not None:
                task["assignee"] = str(assignee).strip()
            if delegated_by is not None:
                task["delegated_by"] = str(delegated_by).strip()
            if parent_task_id is not None:
                task["parent_task_id"] = int(parent_task_id)
            if artifact_dir is not None:
                task["artifact_dir"] = str(artifact_dir).strip()
            if priority is not None:
                task["priority"] = int(priority)
            if max_attempts is not None:
                task["max_attempts"] = max(1, int(max_attempts))
            if lease_owner is not None:
                task["lease_owner"] = str(lease_owner).strip()
            if lease_expires_at is not None:
                task["lease_expires_at"] = float(lease_expires_at)
            if failure_reason is not None:
                task["failure_reason"] = str(failure_reason).strip()
            if artifact_manifest is not None:
                task["artifact_manifest"] = str(artifact_manifest).strip()
            if correlation_id is not None:
                task["correlation_id"] = str(correlation_id).strip()
            if request_id is not None:
                task["request_id"] = str(request_id).strip()
            if session_id is not None:
                task["session_id"] = str(session_id).strip()

            if add_blocked_by:
                merged = set(task.get("blockedBy", []))
                merged.update(int(tid) for tid in add_blocked_by)
                task["blockedBy"] = sorted(merged)

            if add_blocks:
                merged = set(task.get("blocks", []))
                merged.update(int(tid) for tid in add_blocks)
                task["blocks"] = sorted(merged)
                self._update_block_relationship(int(task["id"]), task["blocks"])

            if status is not None:
                clean_status = str(status).strip().lower()
                if clean_status not in VALID_TASK_STATUSES:
                    raise ValueError(f"invalid task status: {status}")
                task["status"] = clean_status
                if clean_status == "completed":
                    self._clear_dependency(int(task["id"]))
                if clean_status in {"completed", "failed", "cancelled"}:
                    task["lease_owner"] = ""
                    task["lease_expires_at"] = 0.0

            task["updated_at"] = time.time()
            self._write_task(task)
            return dict(task)

    def mark_completed(self, task_id: int, owner: str = "") -> Optional[dict[str, Any]]:
        with self._lock:
            path = self._task_path(task_id)
            if not path.exists():
                return None
            task = self._read_task(path)
            if owner and task.get("owner") and task.get("owner") != owner:
                return None
            task["status"] = "completed"
            task["lease_owner"] = ""
            task["lease_expires_at"] = 0.0
            task["updated_at"] = time.time()
            self._write_task(task)
            self._clear_dependency(int(task["id"]))
            return dict(task)

    def get_stats(self) -> dict[str, int]:
        tasks = self.list_tasks()
        stats = {"total": len(tasks)}
        for status in sorted(VALID_TASK_STATUSES):
            stats[status] = 0
        for task in tasks:
            status = task.get("status")
            if status in stats:
                stats[status] += 1
        return stats
