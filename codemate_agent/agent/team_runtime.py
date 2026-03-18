"""
Team Runtime

封装团队协作运行时：inbox、task board、事件日志与上下文注入。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Callable

from codemate_agent.schema import Message
from codemate_agent.team import (
    MessageBus,
    RequestTracker,
    StructuredEventLogger,
    TaskBoard,
)
from codemate_agent.tools.shell.background_tasks import drain_background_notifications


class TeamRuntime:
    def __init__(
        self,
        *,
        enabled: bool,
        workspace_dir: Path,
        team_name: str,
        agent_name: str,
        agent_role: str,
        tool_registry,
        messages: list[Message],
        session_id_provider: Callable[[], str],
        round_provider: Callable[[], int],
        progress_callback: Optional[Callable[[str, dict], None]] = None,
        logger=None,
        task_auto_claim_enabled: bool = False,
        background_tasks_enabled: bool = True,
        identity_reinject_threshold: int = 6,
    ) -> None:
        self.enabled = enabled
        self.workspace_dir = Path(workspace_dir)
        self.team_name = team_name
        self.agent_name = agent_name
        self.agent_role = agent_role
        self.tool_registry = tool_registry
        self.messages = messages
        self.session_id_provider = session_id_provider
        self.round_provider = round_provider
        self.progress_callback = progress_callback
        self.logger = logger
        self.task_auto_claim_enabled = task_auto_claim_enabled
        self.background_tasks_enabled = background_tasks_enabled
        self.identity_reinject_threshold = identity_reinject_threshold
        self._identity_block = (
            f"<identity>You are '{self.agent_name}', role: {self.agent_role}, "
            f"team: {self.team_name}. Keep coordination state consistent.</identity>"
        )

        self.message_bus: Optional[MessageBus] = None
        self.request_tracker: Optional[RequestTracker] = None
        self.task_board: Optional[TaskBoard] = None
        self.team_event_logger: Optional[StructuredEventLogger] = None
        self._active_task_id: Optional[int] = None

        if self.enabled:
            team_dir = self.workspace_dir / ".team"
            self.message_bus = MessageBus(team_dir / "inbox")
            self.request_tracker = RequestTracker()
            self.task_board = TaskBoard(self.workspace_dir / ".tasks")
            self.team_event_logger = StructuredEventLogger(team_dir / "events.jsonl")

    @property
    def active_task_id(self) -> Optional[int]:
        return self._active_task_id

    def emit_event(self, event: str, payload: Optional[dict[str, Any]] = None) -> None:
        if not self.enabled or not self.team_event_logger:
            return
        data = {
            "session_id": self.session_id_provider(),
            "round": self.round_provider(),
            "agent_name": self.agent_name,
            "payload": payload or {},
        }
        try:
            self.team_event_logger.write(event, data)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"写入 team 事件失败: {e}")

    def ensure_identity_block(self, force: bool = False) -> None:
        if not self.enabled:
            return
        marker = "<identity>"
        probe = self.messages[:4]
        if any(msg.role == "system" and marker in (msg.content or "") for msg in probe):
            return
        if (not force) and len(self.messages) > self.identity_reinject_threshold:
            return
        insert_at = 1 if self.messages and self.messages[0].role == "system" else 0
        self.messages.insert(insert_at, Message(role="system", content=self._identity_block))
        self.emit_event("identity_reinjected", {"insert_at": insert_at})

    def ingest_inbox(self) -> None:
        if not self.enabled or not self.message_bus:
            return
        try:
            inbox = self.message_bus.read_inbox(self.agent_name, drain=True)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"读取 team inbox 失败: {e}")
            return
        if not inbox:
            return
        for payload in inbox:
            if self.request_tracker:
                self.request_tracker.ingest_message(payload)
            raw = json.dumps(payload, ensure_ascii=False)
            self.messages.append(
                Message(role="system", content=f"<team_message>{raw}</team_message>")
            )
        self._emit_progress("team_inbox", {"count": len(inbox)})
        self.emit_event("inbox_ingested", {"count": len(inbox)})

    def ingest_background_notifications(self) -> None:
        if not self.background_tasks_enabled:
            return
        try:
            notifications = drain_background_notifications(self.workspace_dir, limit=20)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"读取后台任务通知失败: {e}")
            return
        if not notifications:
            return
        payload = json.dumps(notifications, ensure_ascii=False)
        self.messages.append(
            Message(role="system", content=f"<background_results>{payload}</background_results>")
        )
        self._emit_progress("background_results", {"count": len(notifications)})
        self.emit_event("background_results", {"count": len(notifications)})

    def auto_claim_task(self) -> None:
        if not (self.enabled and self.task_auto_claim_enabled and self.task_board):
            return

        task = None
        newly_claimed = False
        if self._active_task_id is not None:
            task = self.task_board.get_task(self._active_task_id)
            if not task or task.get("status") != "in_progress":
                self._active_task_id = None
                task = None

        if task is None:
            owned = [
                t
                for t in self.task_board.list_tasks()
                if t.get("owner") == self.agent_name and t.get("status") == "in_progress"
            ]
            if owned:
                task = owned[0]
                self._active_task_id = int(task["id"])

        if task is None:
            claimed = self.task_board.claim_first_unclaimed(self.agent_name)
            if claimed:
                task = claimed
                newly_claimed = True
                self._active_task_id = int(task["id"])

        if task is None:
            self.sync_shell_context()
            return

        self.sync_shell_context(task)
        if newly_claimed:
            self.messages.append(
                Message(
                    role="system",
                    content=(
                        f"<auto-claimed>Task #{task['id']}: {task.get('subject', '')}\n"
                        f"{task.get('description', '')}</auto-claimed>"
                    ),
                )
            )
            self.emit_event(
                "task_auto_claimed",
                {"task_id": task["id"], "subject": task.get("subject", "")},
            )

    def sync_shell_context(self, task: Optional[dict[str, Any]] = None) -> None:
        run_shell_tool = self.tool_registry.get("run_shell") if self.tool_registry else None
        if run_shell_tool is None or not hasattr(run_shell_tool, "set_execution_context"):
            return

        if task is None and self.task_board and self._active_task_id is not None:
            task = self.task_board.get_task(self._active_task_id)

        task_id = None
        worktree_dir = None
        if task:
            task_id = task.get("id")
            worktree_dir = task.get("worktree") or None

        try:
            run_shell_tool.set_execution_context(task_id=task_id, worktree_dir=worktree_dir)
        except Exception as e:
            if self.logger:
                self.logger.warning(f"同步 run_shell 执行上下文失败: {e}")

    def complete_active_task(self) -> None:
        if self._active_task_id is None or not self.task_board:
            return
        completed = self.task_board.mark_completed(self._active_task_id, owner=self.agent_name)
        if completed:
            self.emit_event("task_completed", {"task_id": self._active_task_id})
        self._active_task_id = None
        self.sync_shell_context()

    def send_message(
        self,
        *,
        to: str,
        content: str,
        msg_type: str = "message",
        request_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        if not self.enabled or not self.message_bus:
            return None
        payload = self.message_bus.send(
            sender=self.agent_name,
            to=to,
            content=content,
            msg_type=msg_type,
            request_id=request_id,
            extra=extra,
        )
        if self.request_tracker:
            self.request_tracker.ingest_message(payload)
        self.emit_event("message_sent", {"to": to, "type": msg_type})
        return payload

    def get_status(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}
        tracker_snapshot = self.request_tracker.snapshot() if self.request_tracker else {"counts": {}, "pending": {}}
        tasks_stats = self.task_board.get_stats() if self.task_board else {}
        inbox_size = self.message_bus.inbox_size(self.agent_name) if self.message_bus else 0
        return {
            "enabled": True,
            "team_name": self.team_name,
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "active_task_id": self._active_task_id,
            "inbox_pending": inbox_size,
            "task_stats": tasks_stats,
            "request_tracker": tracker_snapshot,
        }

    def peek_inbox(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.enabled or not self.message_bus:
            return []
        messages = self.message_bus.read_inbox(self.agent_name, drain=False)
        return messages[: max(limit, 0)]

    def list_task_board(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.enabled or not self.task_board:
            return []
        tasks = self.task_board.list_tasks()
        return tasks[: max(limit, 0)]

    def reset(self) -> None:
        self._active_task_id = None
        if self.request_tracker:
            self.request_tracker.clear()
        self.sync_shell_context()

    def _emit_progress(self, event: str, data: dict) -> None:
        if not self.progress_callback:
            return
        try:
            self.progress_callback(event, data)
        except Exception as e:
            if self.logger:
                self.logger.debug(f"团队进度回调异常: {e}")
