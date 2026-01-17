"""
Trace 轨迹日志 - 记录完整的 Agent 执行过程

提供会话级别的轨迹记录，支持：
- JSONL 格式输出（机器可读，便于分析）
- Markdown 格式输出（人类可读，便于审查）
- 线程安全的并发写入
"""

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .logger import get_trace_logger


class TraceEventType(str, Enum):
    """轨迹事件类型"""

    # 会话生命周期
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # 用户交互
    USER_INPUT = "user_input"
    USER_CONFIRM = "user_confirm"

    # LLM 交互
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    LLM_ERROR = "llm_error"

    # 工具执行
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"

    # 系统事件
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class TraceEvent:
    """轨迹事件数据结构"""

    event_type: TraceEventType
    payload: dict[str, Any]
    step: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now())

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "ts": self.timestamp.isoformat(),
            "event": self.event_type.value,
            "step": self.step,
            "payload": self.payload,
        }


class TraceLogger:
    """
    Agent 执行轨迹记录器

    记录完整的 Agent 执行过程，包括用户输入、LLM 调用、
    工具执行等所有关键事件。

    Example:
        >>> trace_logger = TraceLogger(
        ...     session_id="s-20260116-123456-abcd",
        ...     trace_dir=Path("logs/traces")
        ... )
        >>> trace_logger.log_event(
        ...     TraceEventType.USER_INPUT,
        ...     {"text": "帮我分析这个项目"}
        ... )
        >>> trace_logger.finalize()
    """

    # 支持的事件类型
    EVENTS = [
        "session_start",
        "session_end",
        "user_input",
        "user_confirm",
        "llm_request",
        "llm_response",
        "llm_error",
        "tool_call",
        "tool_result",
        "tool_error",
        "error",
        "warning",
        "info",
    ]

    def __init__(
        self,
        session_id: str,
        trace_dir: Path,
        enabled: bool = True,
    ):
        """
        初始化 TraceLogger

        Args:
            session_id: 会话唯一标识，格式 s-YYYYMMDD-HHMMSS-xxxx
            trace_dir: 轨迹文件存储目录
            enabled: 是否启用日志记录
        """
        self.session_id = session_id
        self.trace_dir = Path(trace_dir)
        self.enabled = enabled
        self._logger = get_trace_logger()

        # 确保目录存在
        if self.enabled:
            self.trace_dir.mkdir(parents=True, exist_ok=True)

        # 文件路径
        base_name = f"trace-{session_id}"
        self.jsonl_path = self.trace_dir / f"{base_name}.jsonl"
        self.md_path = self.trace_dir / f"{base_name}.md"

        # 内存中的事件缓存
        self._events: list[dict] = []
        self._start_time: datetime = datetime.now()
        self._end_time: Optional[datetime] = None

        # 统计信息
        self._stats: dict[str, Any] = {
            "total_steps": 0,
            "llm_calls": 0,
            "tool_calls": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "errors": 0,
        }

        # 线程锁（保证文件写入安全）
        self._lock = threading.Lock()

        # 写入会话开始事件
        self.log_event(
            TraceEventType.SESSION_START,
            {"session_id": session_id},
            step=0,
        )

    def log_event(
        self,
        event_type: TraceEventType | str,
        payload: dict[str, Any],
        step: int = 0,
    ) -> None:
        """
        记录一个轨迹事件

        Args:
            event_type: 事件类型
            payload: 事件负载数据
            step: 当前执行步数
        """
        if not self.enabled:
            return

        # 统一转换为 TraceEventType
        if isinstance(event_type, str):
            event_type = TraceEventType(event_type)

        event = TraceEvent(
            event_type=event_type,
            payload=payload,
            step=step,
        )

        event_dict = event.to_dict()
        event_dict["session_id"] = self.session_id

        # 更新统计信息
        self._update_stats(event_type, payload)

        with self._lock:
            self._events.append(event_dict)
            self._write_jsonl(event_dict)

    def _update_stats(self, event_type: TraceEventType, payload: dict) -> None:
        """更新统计信息"""
        # 更新步数
        if payload.get("step", 0) > self._stats["total_steps"]:
            self._stats["total_steps"] = payload.get("step", 0)

        # LLM 调用统计
        if event_type == TraceEventType.LLM_REQUEST:
            self._stats["llm_calls"] += 1

        # LLM Token 统计（兼容多种命名格式）
        if event_type == TraceEventType.LLM_RESPONSE:
            usage = payload.get("usage", {})
            if usage:
                # 支持 prompt_tokens/completion_tokens (GLM 格式)
                # 和 input_tokens/output_tokens (通用格式)
                input_tokens = (
                    usage.get("input_tokens") or
                    usage.get("prompt_tokens") or
                    0
                )
                output_tokens = (
                    usage.get("output_tokens") or
                    usage.get("completion_tokens") or
                    0
                )
                self._stats["total_input_tokens"] += input_tokens
                self._stats["total_output_tokens"] += output_tokens

        # 工具调用统计
        if event_type == TraceEventType.TOOL_CALL:
            self._stats["tool_calls"] += 1

        # 错误统计
        if event_type in (TraceEventType.ERROR, TraceEventType.LLM_ERROR, TraceEventType.TOOL_ERROR):
            self._stats["errors"] += 1

    def _write_jsonl(self, event_dict: dict) -> None:
        """写入一行 JSON 到 JSONL 文件"""
        try:
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_dict, ensure_ascii=False) + "\n")
        except Exception as e:
            self._logger.error(f"Failed to write JSONL: {e}")

    def _write_markdown(self) -> None:
        """生成 Markdown 格式的轨迹报告"""
        try:
            with open(self.md_path, "w", encoding="utf-8") as f:
                # 标题
                f.write(f"# CodeMate Agent 执行轨迹\n\n")
                f.write(f"**会话 ID**: `{self.session_id}`\n\n")
                f.write(f"**开始时间**: {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                if self._end_time:
                    duration = (self._end_time - self._start_time).total_seconds()
                    f.write(f"**结束时间**: {self._end_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(f"**执行时长**: {duration:.2f} 秒\n\n")

                # 统计摘要
                f.write("## 📊 统计摘要\n\n")
                f.write("| 指标 | 数值 |\n")
                f.write("|------|------|\n")
                f.write(f"| 总步数 | {self._stats['total_steps']} |\n")
                f.write(f"| LLM 调用 | {self._stats['llm_calls']} |\n")
                f.write(f"| 工具调用 | {self._stats['tool_calls']} |\n")
                f.write(f"| Input Tokens | {self._stats['total_input_tokens']:,} |\n")
                f.write(f"| Output Tokens | {self._stats['total_output_tokens']:,} |\n")
                f.write(f"| 总 Tokens | {self._stats['total_input_tokens'] + self._stats['total_output_tokens']:,} |\n")
                f.write(f"| 错误次数 | {self._stats['errors']} |\n\n")

                # 详细时间线
                f.write("## 📝 执行时间线\n\n")

                current_step = 0
                for event in self._events:
                    event_type = event["event"]
                    step = event.get("step", 0)
                    ts = event["ts"]

                    # 步数标题
                    if step > current_step:
                        f.write(f"\n### Step {step}\n\n")
                        current_step = step

                    # 事件类型图标
                    icon = self._get_event_icon(event_type)
                    f.write(f"#### {icon} {event_type}\n\n")
                    f.write(f"**时间**: {ts}\n\n")

                    # 事件内容
                    payload = event.get("payload", {})
                    f.write(self._format_payload(payload))
                    f.write("\n---\n\n")

                # 文件结束
                f.write(f"\n*生成时间: {datetime.now().isoformat()}*\n")

        except Exception as e:
            self._logger.error(f"Failed to write Markdown: {e}")

    def _get_event_icon(self, event_type: str) -> str:
        """获取事件类型对应的图标"""
        icons = {
            "session_start": "🚀",
            "session_end": "🏁",
            "user_input": "👤",
            "user_confirm": "✅",
            "llm_request": "📤",
            "llm_response": "📥",
            "llm_error": "❌",
            "tool_call": "🔧",
            "tool_result": "✨",
            "tool_error": "⚠️",
            "error": "🔴",
            "warning": "🟡",
            "info": "ℹ️",
        }
        return icons.get(event_type, "📌")

    def _format_payload(self, payload: dict, indent: int = 0) -> str:
        """格式化 payload 内容"""
        if not payload:
            return "*无内容*\n"

        lines = []
        prefix = "    " * indent

        for key, value in payload.items():
            if key == "messages":
                # 消息列表特殊处理
                lines.append(f"{prefix}**{key}**: {len(value)} 条消息\n")
                for i, msg in enumerate(value):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    # 截断长内容
                    if len(content) > 200:
                        content = content[:200] + "..."
                    lines.append(f"{prefix}  {i+1}. [{role}] {content}\n")

            elif isinstance(value, dict):
                lines.append(f"{prefix}**{key}**:\n")
                lines.append(self._format_payload(value, indent + 1))

            elif isinstance(value, list):
                lines.append(f"{prefix}**{key}**: {len(value)} 项\n")

            elif isinstance(value, str):
                # 截断长字符串
                if len(value) > 300:
                    value = value[:300] + "..."
                lines.append(f"{prefix}**{key}**: `{value}`\n")

            else:
                lines.append(f"{prefix}**{key}**: {value}\n")

        return "".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """获取当前统计信息"""
        return {
            "session_id": self.session_id,
            "start_time": self._start_time.isoformat(),
            "end_time": self._end_time.isoformat() if self._end_time else None,
            "duration_seconds": (
                (self._end_time - self._start_time).total_seconds()
                if self._end_time
                else None
            ),
            **self._stats,
        }

    def finalize(self) -> dict[str, Any]:
        """
        结束会话并生成最终报告

        Returns:
            完整的统计信息字典
        """
        self._end_time = datetime.now()

        # 记录会话结束事件
        self.log_event(
            TraceEventType.SESSION_END,
            {
                "duration_seconds": (self._end_time - self._start_time).total_seconds(),
                "stats": self._stats,
            },
            step=self._stats["total_steps"],
        )

        # 生成 Markdown 报告
        if self.enabled:
            self._write_markdown()

        return self.get_stats()


def generate_session_id() -> str:
    """
    生成唯一的会话 ID

    Returns:
        格式为 s-YYYYMMDD-HHMMSS-xxxx 的会话 ID
    """
    import random

    now = datetime.now()
    time_part = now.strftime("%Y%m%d-%H%M%S")
    random_part = "".join(random.choices("0123456789abcdef", k=4))
    return f"s-{time_part}-{random_part}"
