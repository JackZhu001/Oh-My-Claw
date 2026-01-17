"""
会话持久化 - 存储和加载对话历史

使用文件系统存储会话数据，无需数据库。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from ..logging.trace_logger import generate_session_id


@dataclass
class Message:
    """单条消息"""

    role: str  # "user" | "assistant" | "system" | "tool"
    content: str = ""
    tool_name: Optional[str] = None
    tool_result: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        data = {
            "role": self.role,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.content:
            data["content"] = self.content
        if self.tool_name:
            data["tool_name"] = self.tool_name
        if self.tool_result:
            data["tool_result"] = self.tool_result
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """从字典创建"""
        timestamp_str = data.get("timestamp")
        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

        return cls(
            role=data["role"],
            content=data.get("content", ""),
            tool_name=data.get("tool_name"),
            tool_result=data.get("tool_result"),
            timestamp=timestamp,
        )


@dataclass
class SessionMetadata:
    """会话元数据"""

    session_id: str
    created_at: datetime
    updated_at: datetime
    title: str
    message_count: int = 0
    total_tokens: int = 0
    model: str = "glm-4-flash"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "title": self.title,
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionMetadata":
        """从字典创建"""
        return cls(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            title=data["title"],
            message_count=data.get("message_count", 0),
            total_tokens=data.get("total_tokens", 0),
            model=data.get("model", "glm-4-flash"),
        )


class SessionStorage:
    """
    会话存储管理器

    负责单个会话的读写操作。
    """

    def __init__(self, sessions_dir: Path, session_id: Optional[str] = None):
        """
        初始化 SessionStorage

        Args:
            sessions_dir: 会话存储根目录
            session_id: 会话 ID，不指定则生成新 ID
        """
        self.sessions_dir = Path(sessions_dir)
        self.session_id = session_id or generate_session_id()

        # 会话目录
        self.session_dir = self.sessions_dir / self.session_id

        # 文件路径
        self.messages_path = self.session_dir / "messages.jsonl"
        self.metadata_path = self.session_dir / "metadata.json"
        self.summary_path = self.session_dir / "summary.md"

        # 内存缓存
        self._messages: list[Message] = []
        self._metadata: Optional[SessionMetadata] = None

    @classmethod
    def load(cls, sessions_dir: Path, session_id: str) -> "SessionStorage":
        """
        加载已有会话

        Args:
            sessions_dir: 会话存储根目录
            session_id: 要加载的会话 ID

        Returns:
            SessionStorage 实例
        """
        storage = cls(sessions_dir, session_id)
        storage._load_from_disk()
        return storage

    def _load_from_disk(self) -> None:
        """从磁盘加载数据"""
        # 加载元数据
        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self._metadata = SessionMetadata.from_dict(json.load(f))
        else:
            self._metadata = None

        # 加载消息
        self._messages = []
        if self.messages_path.exists():
            with open(self.messages_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._messages.append(Message.from_dict(json.loads(line)))

    def ensure_dir(self) -> None:
        """确保会话目录存在"""
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def add_message(self, message: Message) -> None:
        """添加一条消息"""
        self._messages.append(message)
        self._append_to_file(message)
        # 同步更新元数据中的消息数
        if self._metadata:
            self._metadata.message_count = len(self._messages)
            self._metadata.updated_at = datetime.now()
            self._save_metadata()

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.add_message(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        self.add_message(Message(role="assistant", content=content))

    def add_tool_message(self, tool_name: str, result: str) -> None:
        """添加工具消息"""
        self.add_message(Message(role="tool", tool_name=tool_name, tool_result=result))

    def _append_to_file(self, message: Message) -> None:
        """追加消息到文件"""
        self.ensure_dir()
        with open(self.messages_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message.to_dict(), ensure_ascii=False) + "\n")

    def get_messages(self) -> list[Message]:
        """获取所有消息"""
        return self._messages.copy()

    def set_metadata(self, metadata: SessionMetadata) -> None:
        """设置元数据"""
        self._metadata = metadata
        self._save_metadata()

    def update_metadata(
        self,
        title: Optional[str] = None,
        total_tokens: Optional[int] = None,
    ) -> None:
        """更新元数据"""
        if self._metadata is None:
            now = datetime.now()
            self._metadata = SessionMetadata(
                session_id=self.session_id,
                created_at=now,
                updated_at=now,
                title=title or "新会话",
                message_count=0,
                model="glm-4-flash",
            )

        if title is not None:
            self._metadata.title = title
        if total_tokens is not None:
            self._metadata.total_tokens = total_tokens

        self._metadata.updated_at = datetime.now()
        self._metadata.message_count = len(self._messages)

        self._save_metadata()

    def _save_metadata(self) -> None:
        """保存元数据到文件"""
        if self._metadata:
            self.ensure_dir()
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(self._metadata.to_dict(), f, ensure_ascii=False, indent=2)

    def set_summary(self, summary: str) -> None:
        """设置会话摘要"""
        self.ensure_dir()
        with open(self.summary_path, "w", encoding="utf-8") as f:
            f.write(summary)

    def generate_summary(self, llm_client, final_answer: str = "") -> str:
        """
        生成会话摘要

        使用 LLM 分析对话历史，生成结构化摘要。

        Args:
            llm_client: LLM 客户端
            final_answer: 最终答案（可选）

        Returns:
            生成的摘要文本
        """
        # 构建对话摘要
        conversation = []
        for msg in self._messages:
            if msg.role == "user":
                conversation.append(f"用户: {msg.content}")
            elif msg.role == "assistant" and msg.content:
                conversation.append(f"助手: {msg.content}")
            elif msg.role == "tool":
                conversation.append(f"[工具: {msg.tool_name}]")

        conversation_text = "\n".join(conversation)

        # 构建摘要提示词
        summary_prompt = f"""请分析以下对话，生成简洁的摘要。

对话记录:
{conversation_text}

请按以下格式生成摘要（Markdown 格式）：

## 对话摘要
**任务**: 用户想要完成什么
**过程**: 简要描述执行过程
**结果**: 最终结果或结论

## 关键信息
- 列出 3-5 个关键点

## 使用的工具
- 列出使用过的工具（如果有）
"""

        try:
            # 调用 LLM 生成摘要
            from ..schema import Message

            response = llm_client.complete(
                messages=[Message(role="user", content=summary_prompt)],
                tools=None,
            )

            summary = response.content or "摘要生成失败"

            # 保存摘要
            self.set_summary(summary)

            return summary

        except Exception as e:
            # 失败时返回简单摘要
            simple_summary = f"""## 对话摘要

**任务**: 对话记录
**消息数**: {len(self._messages)}

## 最后回答
{final_answer[:500] if final_answer else "无"}
"""
            self.set_summary(simple_summary)
            return simple_summary

    def get_summary(self) -> Optional[str]:
        """获取会话摘要"""
        if self.summary_path.exists():
            with open(self.summary_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def get_metadata(self) -> Optional[SessionMetadata]:
        """获取元数据"""
        return self._metadata

    def get_messages_for_agent(self) -> list[dict]:
        """
        获取兼容 Agent 格式的消息列表

        将持久化的消息转换为 Agent 可以使用的格式。
        注意：tool 消息会被转换为 agent 格式，但 tool_call 信息无法完全恢复。

        Returns:
            list[dict]: 可用于 Agent 的消息字典列表
        """
        agent_messages = []

        for msg in self._messages:
            if msg.role == "tool":
                # 工具消息需要特殊处理
                # 由于我们只保存了 tool_name 和 tool_result，无法恢复完整的 tool_call_id
                agent_messages.append({
                    "role": "tool",
                    "content": msg.tool_result or "",
                    "name": msg.tool_name,
                    # tool_call_id 需要重新生成，但可能无法关联到原始调用
                    "tool_call_id": f"restored_{msg.timestamp.strftime('%Y%m%d%H%M%S')}",
                })
            else:
                # user, assistant, system 消息直接转换
                agent_messages.append({
                    "role": msg.role,
                    "content": msg.content or "",
                })

        return agent_messages

    def exists(self) -> bool:
        """检查会话是否存在"""
        return self.session_dir.exists()

    def delete(self) -> None:
        """删除会话"""
        import shutil
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir)

    def __repr__(self) -> str:
        return f"SessionStorage(session_id={self.session_id}, messages={len(self._messages)})"
