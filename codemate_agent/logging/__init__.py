"""
CodeMate Agent 日志系统

提供三层日志架构：
1. 基础运行时日志 (Rich 美化输出)
2. Trace 轨迹日志 (JSONL + Markdown)
3. Metrics 统计 (Token、成本、性能)
"""

from .logger import setup_logger, get_logger
from .trace_logger import TraceLogger, TraceEvent, TraceEventType, generate_session_id
from .metrics import SessionMetrics, TokenUsage

__all__ = [
    "setup_logger",
    "get_logger",
    "TraceLogger",
    "TraceEvent",
    "TraceEventType",
    "generate_session_id",
    "SessionMetrics",
    "TokenUsage",
]
