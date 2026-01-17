"""
对话持久化模块

提供基于文件系统的会话存储、索引管理和长期记忆功能。
"""

from .session import (
    Message,
    SessionMetadata,
    SessionStorage,
)

from .index import (
    SessionIndex,
    SessionIndexEntry,
)

from .memory import (
    MemoryManager,
)

__all__ = [
    # Session
    "Message",
    "SessionMetadata",
    "SessionStorage",
    # Index
    "SessionIndex",
    "SessionIndexEntry",
    # Memory
    "MemoryManager",
]
