"""
Memory Read 工具 - 主动查询长期记忆

Agent 可通过此工具在需要时按关键词检索长期记忆，
补充 system prompt 中未自动注入的内容。
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, Optional

from codemate_agent.tools.base import Tool


class MemoryReadTool(Tool):
    """
    长期记忆检索工具

    基于 BM25 关键词检索，返回最相关的记忆片段。
    使用 ClassVar 存储 MemoryManager 引用，由 Agent 初始化时注入。
    """

    _memory_manager: ClassVar[Optional[Any]] = None  # MemoryManager

    @classmethod
    def set_dependencies(cls, memory_manager: Any) -> None:
        """注入 MemoryManager 依赖（由 Agent.__init__ 调用）"""
        cls._memory_manager = memory_manager

    @property
    def name(self) -> str:
        return "memory_read"

    @property
    def description(self) -> str:
        return """按关键词检索长期记忆，返回最相关的片段。

何时调用：
- 用户问到"上次"、"之前说的"、"你记得吗"等涉及历史信息的问题
- 需要了解用户偏好或项目约定但当前 context 中没有相关信息
- 开始新任务前，确认是否有相关的已知 Bug 或约定

参数：
- query: 检索关键词，如 "测试框架"、"用户偏好"、"已知 Bug"
- top_k: 返回最多几条结果（默认 3，最大 5）"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量（默认 3，最大 5）",
                },
            },
            "required": ["query"],
        }

    def run(self, **kwargs) -> str:
        query: str = kwargs.get("query", "").strip()
        top_k_raw = kwargs.get("top_k", 3)
        try:
            top_k = max(1, min(int(top_k_raw), 5))
        except (ValueError, TypeError):
            top_k = 3

        if not query:
            return "❌ memory_read 错误：query 不能为空"

        if MemoryReadTool._memory_manager is None:
            return "❌ memory_read 错误：MemoryManager 未初始化（请确认记忆功能已启用）"

        try:
            result = MemoryReadTool._memory_manager.retrieve_relevant_memory(
                query, top_k=top_k
            )
            return result or "📭 未找到相关记忆"
        except Exception as e:
            return f"❌ memory_read 检索失败：{e}"
