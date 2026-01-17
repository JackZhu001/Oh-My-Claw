"""
会话索引管理 - 快速检索所有会话
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .session import SessionStorage, SessionMetadata


@dataclass
class SessionIndexEntry:
    """会话索引条目"""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    model: str

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "model": self.model,
        }

    @classmethod
    def from_metadata(cls, metadata: SessionMetadata) -> "SessionIndexEntry":
        """从元数据创建索引条目"""
        return cls(
            session_id=metadata.session_id,
            title=metadata.title,
            created_at=metadata.created_at.isoformat(),
            updated_at=metadata.updated_at.isoformat(),
            message_count=metadata.message_count,
            model=metadata.model,
        )


class SessionIndex:
    """
    会话索引管理器

    维护所有会话的索引，支持快速检索和排序。
    """

    INDEX_FILE = "sessions_index.json"

    def __init__(self, sessions_dir: Path):
        """
        初始化 SessionIndex

        Args:
            sessions_dir: 会话存储根目录
        """
        self.sessions_dir = Path(sessions_dir)
        self.index_path = self.sessions_dir / self.INDEX_FILE
        self._entries: dict[str, SessionIndexEntry] = {}

        self._load()

    def _load(self) -> None:
        """从磁盘加载索引"""
        if not self.index_path.exists():
            return

        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for entry_data in data.get("sessions", []):
                entry = SessionIndexEntry(
                    session_id=entry_data["session_id"],
                    title=entry_data["title"],
                    created_at=entry_data["created_at"],
                    updated_at=entry_data["updated_at"],
                    message_count=entry_data.get("message_count", 0),
                    model=entry_data.get("model", "glm-4-flash"),
                )
                self._entries[entry.session_id] = entry
        except (json.JSONDecodeError, KeyError):
            # 索引文件损坏，重新扫描
            self._rebuild()

    def _save(self) -> None:
        """保存索引到磁盘"""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "updated_at": datetime.now().isoformat(),
            "sessions": [e.to_dict() for e in self._entries.values()],
        }

        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _rebuild(self) -> None:
        """重建索引（扫描所有会话目录）"""
        self._entries.clear()

        if not self.sessions_dir.exists():
            return

        for session_dir in self.sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue

            metadata_path = session_dir / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = SessionMetadata.from_dict(json.load(f))

                    entry = SessionIndexEntry.from_metadata(metadata)
                    self._entries[entry.session_id] = entry
                except (json.JSONDecodeError, KeyError):
                    continue

        self._save()

    def update(self, metadata: SessionMetadata) -> None:
        """
        更新索引条目

        Args:
            metadata: 会话元数据
        """
        entry = SessionIndexEntry.from_metadata(metadata)
        self._entries[metadata.session_id] = entry
        self._save()

    def remove(self, session_id: str) -> None:
        """
        移除索引条目

        Args:
            session_id: 会话 ID
        """
        if session_id in self._entries:
            del self._entries[session_id]
            self._save()

    def get(self, session_id: str) -> Optional[SessionIndexEntry]:
        """
        获取索引条目

        Args:
            session_id: 会话 ID

        Returns:
            索引条目，不存在返回 None
        """
        return self._entries.get(session_id)

    def list_all(
        self,
        limit: int = 50,
        sort_by: str = "updated_at",
        reverse: bool = True,
    ) -> list[SessionIndexEntry]:
        """
        列出所有会话

        Args:
            limit: 最大返回数量
            sort_by: 排序字段 (created_at, updated_at, title)
            reverse: 是否倒序

        Returns:
            会话索引条目列表
        """
        entries = list(self._entries.values())

        # 排序
        if sort_by in ("created_at", "updated_at", "title"):
            entries.sort(key=lambda e: getattr(e, sort_by), reverse=reverse)
        else:
            entries.sort(key=lambda e: e.updated_at, reverse=True)

        return entries[:limit]

    def list_recent(self, limit: int = 10) -> list[SessionIndexEntry]:
        """
        列出最近会话

        Args:
            limit: 最大返回数量

        Returns:
            最近更新的会话列表
        """
        return self.list_all(limit=limit, sort_by="updated_at", reverse=True)

    def search(self, keyword: str, limit: int = 10) -> list[SessionIndexEntry]:
        """
        搜索会话

        Args:
            keyword: 搜索关键词
            limit: 最大返回数量

        Returns:
            匹配的会话列表
        """
        keyword_lower = keyword.lower()

        results = [
            e for e in self._entries.values()
            if keyword_lower in e.title.lower()
        ]

        results.sort(key=lambda e: e.updated_at, reverse=True)
        return results[:limit]

    def count(self) -> int:
        """获取会话总数"""
        return len(self._entries)

    def __repr__(self) -> str:
        return f"SessionIndex(sessions={len(self._entries)})"
