"""
任务板工具（s07 对齐）

提供持久化任务 CRUD 与依赖管理能力，底层存储在 .tasks/task_*.json。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from codemate_agent.team import MessageBus, TaskBoard
from codemate_agent.tools.base import Tool


_BOARDS: dict[str, TaskBoard] = {}
_BOARDS_LOCK = threading.Lock()


def _get_board(workspace_dir: Path) -> TaskBoard:
    key = str(workspace_dir.resolve())
    with _BOARDS_LOCK:
        board = _BOARDS.get(key)
        if board is None:
            board = TaskBoard(workspace_dir / ".tasks")
            _BOARDS[key] = board
        return board


class _TaskBoardToolBase:
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()

    @property
    def board(self) -> TaskBoard:
        return _get_board(self.workspace_dir)


class TaskCreateTool(_TaskBoardToolBase, Tool):
    @property
    def name(self) -> str:
        return "task_create"

    @property
    def description(self) -> str:
        return """创建持久化任务（写入 .tasks 目录）。

参数:
- subject: 任务标题（必填）
- description: 任务描述（可选）
- blocked_by: 依赖任务 ID 列表（可选）
- blocks: 被当前任务阻塞的任务 ID 列表（可选）
- namespace: 任务命名空间（可选；会自动前缀到标题，如 ITEST:）"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "任务标题"},
                "description": {"type": "string", "description": "任务描述"},
                "blocked_by": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "依赖任务 ID 列表",
                },
                "blocks": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "被当前任务阻塞的任务 ID 列表",
                },
                "namespace": {
                    "type": "string",
                    "description": "任务命名空间（可选，如 ITEST）",
                },
            },
            "required": ["subject"],
        }

    def run(
        self,
        subject: str,
        description: str = "",
        blocked_by: Optional[list[int]] = None,
        blocks: Optional[list[int]] = None,
        namespace: str = "",
        **kwargs,
    ) -> str:
        try:
            normalized_blocked = [int(tid) for tid in (blocked_by or [])]
            normalized_blocks = [int(tid) for tid in (blocks or [])]
            clean_namespace = (namespace or "").strip()
            clean_subject = (subject or "").strip()
            if clean_namespace and clean_subject:
                prefix = f"{clean_namespace}:"
                if not clean_subject.startswith(prefix):
                    clean_subject = f"{prefix} {clean_subject}"
            task = self.board.create_task(
                subject=clean_subject,
                description=description,
                blocked_by=normalized_blocked,
                blocks=normalized_blocks,
            )
            return json.dumps(task, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"错误: 创建任务失败: {e}"


class TaskGetTool(_TaskBoardToolBase, Tool):
    @property
    def name(self) -> str:
        return "task_get"

    @property
    def description(self) -> str:
        return "按 ID 读取任务详情。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "任务 ID"},
            },
            "required": ["task_id"],
        }

    def run(self, task_id: int, **kwargs) -> str:
        task = self.board.get_task(task_id)
        if task is None:
            return f"错误: 任务不存在: {task_id}"
        return json.dumps(task, ensure_ascii=False, indent=2)


class TaskUpdateTool(_TaskBoardToolBase, Tool):
    @property
    def name(self) -> str:
        return "task_update"

    @property
    def description(self) -> str:
        return """更新任务状态、负责人和依赖关系。

参数:
- task_id: 任务 ID（必填）
- status: pending | in_progress | completed | cancelled（可选）
- owner: 负责人（可选）
- add_blocked_by: 追加依赖任务 ID 列表（可选）
- add_blocks: 追加被阻塞任务 ID 列表（可选）"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "任务 ID"},
                "status": {
                    "type": "string",
                    "enum": [
                        "pending",
                        "leased",
                        "in_progress",
                        "blocked",
                        "review",
                        "completed",
                        "failed",
                        "cancelled",
                    ],
                    "description": "任务状态",
                },
                "owner": {"type": "string", "description": "负责人"},
                "add_blocked_by": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "追加依赖任务 ID 列表",
                },
                "add_blocks": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "追加被阻塞任务 ID 列表",
                },
            },
            "required": ["task_id"],
        }

    def run(
        self,
        task_id: int,
        status: str = None,
        owner: str = None,
        add_blocked_by: Optional[list[int]] = None,
        add_blocks: Optional[list[int]] = None,
        **kwargs,
    ) -> str:
        try:
            task = self.board.update_task(
                task_id=task_id,
                status=status,
                owner=owner,
                add_blocked_by=add_blocked_by,
                add_blocks=add_blocks,
            )
            if task is None:
                return f"错误: 任务不存在: {task_id}"
            return json.dumps(task, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"错误: 更新任务失败: {e}"


class TaskListTool(_TaskBoardToolBase, Tool):
    @property
    def name(self) -> str:
        return "task_list"

    @property
    def description(self) -> str:
        return "列出任务板任务（含状态、负责人、依赖信息），可按 namespace 过滤。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "命名空间前缀过滤（可选）"},
            },
        }

    def run(self, namespace: str = "", **kwargs) -> str:
        tasks = self.board.list_tasks()
        clean_namespace = (namespace or "").strip()
        if clean_namespace:
            prefix = f"{clean_namespace}:"
            tasks = [
                task for task in tasks
                if str(task.get("subject", "")).startswith(prefix)
            ]
        if not tasks:
            return "No tasks."
        lines = []
        for task in tasks:
            marker = {
                "pending": "[ ]",
                "leased": "[L]",
                "in_progress": "[>]",
                "blocked": "[!]",
                "review": "[R]",
                "completed": "[x]",
                "failed": "[f]",
                "cancelled": "[~]",
            }.get(task.get("status"), "[?]")
            owner = f" @{task.get('owner')}" if task.get("owner") else ""
            blocked = f" (blockedBy: {task.get('blockedBy', [])})" if task.get("blockedBy") else ""
            lines.append(f"{marker} #{task.get('id')}: {task.get('subject', '')}{owner}{blocked}")
        return "\n".join(lines)


class TaskCleanupTool(_TaskBoardToolBase, Tool):
    @property
    def name(self) -> str:
        return "task_cleanup"

    @property
    def description(self) -> str:
        return """清理任务板数据。

参数:
- namespace: 按命名空间前缀删除（如 ITEST）
- all_tasks: 是否删除所有任务（默认 false）"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "命名空间前缀（可选）"},
                "all_tasks": {"type": "boolean", "description": "是否删除全部任务（默认 false）"},
            },
        }

    def run(self, namespace: str = "", all_tasks: bool = False, **kwargs) -> str:
        if isinstance(all_tasks, str):
            all_tasks = all_tasks.strip().lower() in {"1", "true", "yes", "y"}
        clean_namespace = (namespace or "").strip()
        if not all_tasks and not clean_namespace:
            return "错误: 需要提供 namespace 或将 all_tasks 设为 true"
        prefix = f"{clean_namespace}:" if clean_namespace else ""
        deleted = self.board.cleanup_tasks(subject_prefix=prefix, all_tasks=bool(all_tasks))
        return json.dumps(
            {
                "deleted_count": len(deleted),
                "deleted_task_ids": deleted,
                "namespace": clean_namespace,
                "all_tasks": bool(all_tasks),
            },
            ensure_ascii=False,
            indent=2,
        )


class TeamStatusTool(_TaskBoardToolBase, Tool):
    @property
    def name(self) -> str:
        return "team_status"

    @property
    def description(self) -> str:
        return "读取团队运行时摘要（team/inbox/task stats 与最近事件）。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_limit": {"type": "integer", "description": "最近事件条数（默认 10）"},
            },
        }

    def run(self, event_limit: int = 10, **kwargs) -> str:
        team_enabled = os.getenv("TEAM_AGENT_ENABLED", "false").lower() == "true"
        team_name = os.getenv("TEAM_NAME", "default")
        agent_name = os.getenv("TEAM_AGENT_NAME", "lead")
        agent_role = os.getenv("TEAM_AGENT_ROLE", "lead")

        team_dir = self.workspace_dir / ".team"
        bus = MessageBus(team_dir / "inbox")
        inbox_pending = bus.inbox_size(agent_name)
        task_stats = self.board.get_stats()

        events_path = team_dir / "events.jsonl"
        recent_events: list[str] = []
        total_events = 0
        if events_path.exists():
            lines = events_path.read_text(encoding="utf-8").splitlines()
            total_events = len(lines)
            safe_limit = max(1, min(int(event_limit or 10), 50))
            for raw in lines[-safe_limit:]:
                try:
                    payload = json.loads(raw)
                    recent_events.append(str(payload.get("event", "")))
                except json.JSONDecodeError:
                    continue

        return json.dumps(
            {
                "enabled": team_enabled,
                "team_name": team_name,
                "agent_name": agent_name,
                "agent_role": agent_role,
                "inbox_pending": inbox_pending,
                "task_stats": task_stats,
                "events_total": total_events,
                "recent_events": recent_events,
            },
            ensure_ascii=False,
            indent=2,
        )
