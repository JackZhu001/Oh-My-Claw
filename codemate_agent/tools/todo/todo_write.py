"""
TodoWrite 工具 - 任务列表管理

参考设计：
- 声明式更新：LLM 提交完整列表，工具负责 diff
- 低心智负担：模型不维护 id，只提交 content + status
- UI 分离：data 面向模型，text 面向用户
"""

from typing import Any, Dict, List
from pathlib import Path

from codemate_agent.tools.base import Tool


# 有效的任务状态
VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}

# 约束常量
MAX_TODO_COUNT = 10
MAX_CONTENT_LENGTH = 60


class TodoWriteTool(Tool):
    """
    任务列表管理工具

    支持声明式覆盖更新任务列表。
    """

    # 状态图标
    STATUS_ICONS = {
        "pending": "[ ]",
        "in_progress": "[▶]",
        "completed": "[✓]",
        "cancelled": "[~]",
    }

    def __init__(self, working_dir: str = "."):
        """初始化 TodoWrite 工具"""
        self._working_dir = working_dir

    @property
    def name(self) -> str:
        return "todo_write"

    @property
    def description(self) -> str:
        return """管理任务列表。

支持的操作：
- 创建/更新任务列表
- 更新任务状态
- 显示进度

参数：
- summary: 总体任务概述（必填）
- todos: 任务列表，每项包含 {content: string, status: pending|in_progress|completed|cancelled}（必填）

约束：
- 最多 10 个任务
- 每个任务最多 60 字符
- 同时只能有 1 个 in_progress 状态的任务

返回格式化的任务列表显示。"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "总体任务概述"
                },
                "todos": {
                    "type": "array",
                    "description": "任务列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "任务内容"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed", "cancelled"],
                                "description": "任务状态"
                            }
                        },
                        "required": ["content"]
                    }
                }
            },
            "required": ["summary", "todos"]
        }

    def run(self, **kwargs) -> str:
        """
        执行任务列表更新

        Args:
            summary: 总体任务概述
            todos: 任务列表

        Returns:
            格式化的响应字符串
        """
        summary = kwargs.get("summary", "")
        todos = kwargs.get("todos", [])

        # 防护：确保 todos 是列表
        if not isinstance(todos, list):
            return self._error(f"todos 必须是数组，实际收到 {type(todos).__name__}")

        # 参数校验
        if not summary:
            return self._error("summary 参数不能为空")

        if not isinstance(todos, list):
            return self._error("todos 必须是数组")

        if len(todos) > MAX_TODO_COUNT:
            return self._error(f"最多支持 {MAX_TODO_COUNT} 个任务")

        # 验证并生成任务列表
        validated_todos = []
        in_progress_count = 0

        for idx, item in enumerate(todos):
            # 确保 item 是字典
            if not isinstance(item, dict):
                continue

            try:
                content = item.get("content", "")
                status = item.get("status", "pending")

                # content 必填
                if not content:
                    continue

                # 确保 content 和 status 是字符串
                if not isinstance(content, str):
                    content = str(content)
                if not isinstance(status, str):
                    status = "pending"

                content = content.strip()[:MAX_CONTENT_LENGTH]

                # status 默认为 pending
                if status not in VALID_STATUSES:
                    status = "pending"

                # 统计 in_progress
                if status == "in_progress":
                    in_progress_count += 1

                validated_todos.append({
                    "id": f"t{idx + 1}",
                    "content": content,
                    "status": status,
                })
            except Exception as e:
                # 跳过有问题的项目
                import logging
                logging.getLogger(__name__).warning(f"处理任务 {idx} 时出错: {e}")
                continue

        # 约束：最多一个 in_progress
        if in_progress_count > 1:
            return self._error("同时只能有 1 个进行中的任务")

        # 生成统计
        stats = self._get_stats(validated_todos)

        # 生成响应
        return self._format_response(
            todos=validated_todos,
            summary=summary,
            stats=stats,
        )

    def _get_stats(self, todos: List[Dict]) -> Dict[str, int]:
        """获取任务统计"""
        return {
            "total": len(todos),
            "pending": sum(1 for t in todos if t["status"] == "pending"),
            "in_progress": sum(1 for t in todos if t["status"] == "in_progress"),
            "completed": sum(1 for t in todos if t["status"] == "completed"),
            "cancelled": sum(1 for t in todos if t["status"] == "cancelled"),
        }

    def _format_response(
        self,
        todos: List[Dict],
        summary: str,
        stats: Dict[str, int],
    ) -> str:
        """格式化响应"""
        lines = []
        lines.append("--- TODO UPDATE ---")
        lines.append(f"任务: {summary}")

        for todo in todos:
            icon = self.STATUS_ICONS.get(todo["status"], "[ ]")
            lines.append(f"{icon} {todo['content']}")

        # 统计行
        done = stats["completed"] + stats["cancelled"]
        lines.append(f"--- [{done}/{stats['total']}] 完成 ---")

        return "\n".join(lines)

    def _error(self, message: str) -> str:
        """返回错误信息"""
        return f"❌ TodoWrite 错误: {message}"
