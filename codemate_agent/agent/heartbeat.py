"""
Heartbeat 监控器

将心跳逻辑从 Agent 中抽离，便于复用和测试。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple, Dict, Any


class HeartbeatMonitor:
    def __init__(
        self,
        *,
        session_id: str,
        heartbeat_dir: Path,
        enabled: bool,
        timeout_seconds: int,
        mode: str,
        poll_seconds: int,
        progress_callback: Optional[Callable[[str, dict], None]],
        logger,
        state_provider: Callable[[], Dict[str, Any]],
        todo_stats_provider: Optional[Callable[[], Tuple[int, int]]] = None,
        todo_nag_enabled: bool = False,
    ) -> None:
        self.enabled = enabled
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.mode = mode or "task_polling"
        self.verbose = self.mode == "verbose"
        self.poll_seconds = max(0, int(poll_seconds))
        self.progress_callback = progress_callback
        self.logger = logger
        self.state_provider = state_provider
        self.todo_stats_provider = todo_stats_provider
        self.todo_nag_enabled = todo_nag_enabled

        heartbeat_dir = Path(heartbeat_dir)
        heartbeat_dir.mkdir(parents=True, exist_ok=True)
        self._heartbeat_file = heartbeat_dir / f"heartbeat-{session_id}.jsonl"

        now = time.time()
        self._heartbeat_state = {
            "session_id": session_id,
            "phase": "idle",
            "beats": 0,
            "last_beat_ts": now,
            "last_tool": "",
            "last_alert": "",
            "stalled": False,
            "last_todo_check_ts": 0.0,
            "pending_todos": 0,
        }
        self._last_activity_ts = now
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def emit(self, phase: str, source: str = "", **extra) -> None:
        if not self.enabled:
            return
        if (not self.verbose) and source != "worker":
            key_phases = {"completed", "max_rounds", "watchdog_alert", "todo_nudge"}
            if phase not in key_phases:
                return

        now = time.time()
        self._heartbeat_state["phase"] = phase
        self._heartbeat_state["last_beat_ts"] = now
        self._heartbeat_state["beats"] += 1
        self._heartbeat_state["last_tool"] = extra.get("tool", self._heartbeat_state["last_tool"])
        self._heartbeat_state["stalled"] = extra.get("stalled", self._heartbeat_state["stalled"])
        if extra.get("alert"):
            self._heartbeat_state["last_alert"] = extra.get("message", "")

        state = self.state_provider() if self.state_provider else {}
        payload = {
            "ts": now,
            "session_id": self._heartbeat_state["session_id"],
            "phase": phase,
            "source": source,
            "round": state.get("round", 0),
            "message_count": state.get("message_count", 0),
            "total_tokens": state.get("total_tokens", 0),
            "last_tool": self._heartbeat_state["last_tool"],
            "stalled": self._heartbeat_state["stalled"],
            **extra,
        }

        if source != "worker":
            self._last_activity_ts = now

        try:
            with open(self._heartbeat_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e:
            self.logger.debug(f"写入心跳日志失败: {e}")

        self._emit_progress("heartbeat", payload)

    def check_timeout(self, operation: str, duration_ms: float) -> None:
        if not self.enabled:
            return
        timeout_ms = self.timeout_seconds * 1000
        if duration_ms <= timeout_ms:
            return
        message = (
            f"心跳告警: {operation} 执行耗时 {duration_ms/1000:.2f}s，"
            f"超过阈值 {self.timeout_seconds}s"
        )
        self.logger.warning(message)
        self.emit(
            "watchdog_alert",
            source="watchdog",
            alert=True,
            stalled=True,
            operation=operation,
            duration_ms=round(duration_ms, 2),
            message=message,
        )
        self._emit_progress("heartbeat_alert", {"operation": operation, "duration_ms": round(duration_ms, 2)})

    def start_worker(self) -> None:
        if not self.enabled or self.poll_seconds <= 0:
            return

        def _worker_loop() -> None:
            while not self._stop_event.is_set():
                self._stop_event.wait(self.poll_seconds)
                if self._stop_event.is_set():
                    break
                self._pending_check_once()

        self._thread = threading.Thread(
            target=_worker_loop,
            name="codemate-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def get_status(self) -> dict:
        state = dict(self._heartbeat_state)
        state["age_seconds"] = round(time.time() - state["last_beat_ts"], 2)
        state["timeout_seconds"] = self.timeout_seconds
        state["enabled"] = self.enabled
        state["mode"] = self.mode
        state["idle_seconds"] = round(time.time() - self._last_activity_ts, 2)
        return state

    def _pending_check_once(self) -> None:
        pending = 0
        in_progress = 0
        if self.todo_stats_provider:
            try:
                pending, in_progress = self.todo_stats_provider()
            except Exception:
                pending, in_progress = 0, 0

        now = time.time()
        idle_seconds = now - self._last_activity_ts
        self._heartbeat_state["last_todo_check_ts"] = now
        self._heartbeat_state["pending_todos"] = pending + in_progress

        self.emit(
            "heartbeat_tick",
            source="worker",
            pending_todos=pending,
            in_progress_todos=in_progress,
            idle_seconds=round(idle_seconds, 2),
        )

        if (
            self.todo_nag_enabled
            and (pending + in_progress) > 0
            and idle_seconds > self.timeout_seconds
        ):
            message = (
                f"检测到待办未清空（pending={pending}, in_progress={in_progress}），"
                f"且空闲 {idle_seconds:.1f}s"
            )
            self.emit(
                "todo_nudge",
                source="worker",
                alert=True,
                message=message,
                pending_todos=pending,
                in_progress_todos=in_progress,
                idle_seconds=round(idle_seconds, 2),
            )
            self._emit_progress(
                "heartbeat_todo_nudge",
                {"pending": pending, "in_progress": in_progress, "idle_seconds": round(idle_seconds, 2)},
            )

    def _emit_progress(self, event: str, data: dict) -> None:
        if not self.progress_callback:
            return
        try:
            self.progress_callback(event, data)
        except Exception as e:
            self.logger.debug(f"心跳进度回调异常: {e}")
