"""
后台任务工具（s08 对齐）

提供 background_run / check_background，并支持通知回注。
"""

from __future__ import annotations

import os
import shlex
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from codemate_agent.tools.base import Tool
from codemate_agent.tools.shell.run_shell import RunShellTool


class _BackgroundTaskManager:
    DEFAULT_TIMEOUT = 120
    MAX_TIMEOUT = 300
    MAX_RESULT_PREVIEW = 500

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir.resolve()
        self.runner = RunShellTool(workspace_dir=str(self.workspace_dir))
        self.strict_sequence = os.getenv("BACKGROUND_STRICT_SEQUENCE", "true").lower() == "true"
        self._tasks: dict[str, dict[str, Any]] = {}
        self._notification_queue: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._last_started_task_id: str = ""
        self._last_checked_task_id: str = ""

    @staticmethod
    def _normalize_command(command: str) -> str:
        clean = " ".join((command or "").strip().split())
        if not clean:
            return ""
        try:
            return " ".join(shlex.split(clean))
        except ValueError:
            return " ".join(clean.split())

    def start(
        self,
        command: str,
        timeout: int = DEFAULT_TIMEOUT,
        allow_parallel: bool = False,
    ) -> str:
        clean_command = (command or "").strip()
        if not clean_command:
            return "错误: command 参数不能为空"

        try:
            safe_timeout = max(1, min(int(timeout), self.MAX_TIMEOUT))
        except Exception:
            safe_timeout = self.DEFAULT_TIMEOUT

        normalized = self._normalize_command(clean_command)
        with self._lock:
            if (
                self.strict_sequence
                and self._last_started_task_id
                and self._last_checked_task_id != self._last_started_task_id
            ):
                prev_task = self._tasks.get(self._last_started_task_id)
                if prev_task is not None:
                    return (
                        f"请先检查上一个后台任务状态: {self._last_started_task_id}。\n"
                        f"先执行 check_background(task_id='{self._last_started_task_id}') 再启动新任务。\n"
                        f"NEXT_ACTION: check_background(task_id='{self._last_started_task_id}')"
                    )

            running_tasks = [task for task in self._tasks.values() if task.get("status") == "running"]
            for task in running_tasks:
                task_key = str(task.get("command_key") or self._normalize_command(str(task.get("command", ""))))
                if task_key == normalized:
                    existing_id = task.get("task_id", "")
                    return (
                        f"Background task {existing_id} already running: {task.get('command', '')[:80]}\n"
                        f"Use check_background(task_id='{existing_id}') to poll status.\n"
                        f"NEXT_ACTION: check_background(task_id='{existing_id}')"
                    )

            if running_tasks and not allow_parallel:
                current = running_tasks[0]
                current_id = current.get("task_id", "")
                return (
                    f"已有后台任务运行中: {current_id}。\n"
                    f"请先执行 check_background(task_id='{current_id}')；"
                    f"如需并行请设置 allow_parallel=true。\n"
                    f"NEXT_ACTION: check_background(task_id='{current_id}')"
                )

            task_id = uuid.uuid4().hex[:8]
            self._tasks[task_id] = {
                "task_id": task_id,
                "status": "running",
                "command": clean_command,
                "command_key": normalized,
                "timeout": safe_timeout,
                "result": "",
                "started_at": time.time(),
                "finished_at": None,
            }
            self._last_started_task_id = task_id
            self._last_checked_task_id = ""

        thread = threading.Thread(
            target=self._execute,
            args=(task_id, clean_command, safe_timeout),
            daemon=True,
        )
        thread.start()
        return f"Background task {task_id} started: {clean_command[:80]}"

    def _execute(self, task_id: str, command: str, timeout: int) -> None:
        output = self.runner.run(command=command, timeout=timeout, _background=True)
        status = self._classify_status(output)
        finished_at = time.time()

        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task["status"] = status
            task["result"] = output
            task["finished_at"] = finished_at
            self._notification_queue.append(
                {
                    "task_id": task_id,
                    "status": status,
                    "command": command[:120],
                    "result": (output or "(no output)")[: self.MAX_RESULT_PREVIEW],
                }
            )

    def _classify_status(self, output: str) -> str:
        text = str(output or "")
        if text.startswith("错误:"):
            return "error"
        if "[退出码:" in text:
            return "failed"
        return "completed"

    def check(self, task_id: Optional[str] = None) -> str:
        with self._lock:
            if task_id:
                task = self._tasks.get(task_id)
                if not task:
                    return f"错误: 未找到后台任务: {task_id}"
                self._last_checked_task_id = task_id
                if task["status"] == "running":
                    return f"[running] {task['command'][:80]}\n(running)"
                return f"[{task['status']}] {task['command'][:80]}\n{task.get('result') or '(no output)'}"

            if not self._tasks:
                return "No background tasks."
            lines = []
            for task in self._tasks.values():
                lines.append(
                    f"{task['task_id']}: [{task['status']}] {task['command'][:60]}"
                )
            return "\n".join(lines)

    def drain_notifications(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(0, int(limit or 0))
        if safe_limit == 0:
            return []
        with self._lock:
            drained = self._notification_queue[:safe_limit]
            del self._notification_queue[:safe_limit]
        return drained


_MANAGERS: dict[str, _BackgroundTaskManager] = {}
_MANAGERS_LOCK = threading.Lock()


def _get_manager(workspace_dir: Path | str | None) -> _BackgroundTaskManager:
    root = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()
    key = str(root)
    with _MANAGERS_LOCK:
        manager = _MANAGERS.get(key)
        if manager is None:
            manager = _BackgroundTaskManager(root)
            _MANAGERS[key] = manager
        return manager


def drain_background_notifications(workspace_dir: Path | str, limit: int = 20) -> list[dict[str, Any]]:
    return _get_manager(workspace_dir).drain_notifications(limit=limit)


class BackgroundRunTool(Tool):
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()

    @property
    def name(self) -> str:
        return "background_run"

    @property
    def description(self) -> str:
        return """后台执行 shell 命令并立即返回 task_id。

参数:
- command: 要执行的命令（必填）
- timeout: 超时秒数（可选，默认 120，最大 300）
- allow_parallel: 是否允许与当前 running 任务并行（可选，默认 false）"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要后台执行的命令"},
                "timeout": {"type": "integer", "description": "超时秒数（默认 120）"},
                "allow_parallel": {
                    "type": "boolean",
                    "description": "是否允许并行启动后台任务（默认 false）",
                },
            },
            "required": ["command"],
        }

    def run(self, command: str, timeout: int = 120, allow_parallel: bool = False, **kwargs) -> str:
        if isinstance(allow_parallel, str):
            allow_parallel = allow_parallel.strip().lower() in {"1", "true", "yes", "y"}
        manager = _get_manager(self.workspace_dir)
        return manager.start(command=command, timeout=timeout, allow_parallel=bool(allow_parallel))


class CheckBackgroundTool(Tool):
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()

    @property
    def name(self) -> str:
        return "check_background"

    @property
    def description(self) -> str:
        return "查询后台任务状态；不传 task_id 时返回所有任务摘要。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "后台任务 ID（可选）"},
            },
        }

    def run(self, task_id: str = "", **kwargs) -> str:
        manager = _get_manager(self.workspace_dir)
        clean_task_id = (task_id or "").strip()
        return manager.check(clean_task_id or None)
