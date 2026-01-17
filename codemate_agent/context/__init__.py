"""
上下文工程模块

管理对话历史，防止上下文窗口溢出。
"""

from .compressor import ContextCompressor, CompressionConfig
from .truncator import ObservationTruncator, get_truncator

__all__ = [
    "ContextCompressor",
    "CompressionConfig",
    "ObservationTruncator",
    "get_truncator",
]
