"""
子代理运行器

从 TaskTool 中拆分出的独立执行器，负责运行子代理会话与输出统一结果。
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from codemate_agent.llm.client import LLMClient as GLMClient
from codemate_agent.prompts.agents_prompts import get_subagent_prompt
from codemate_agent.schema import Message
from codemate_agent.tools.registry import ToolRegistry
from codemate_agent.validation import ArgumentValidator

logger = logging.getLogger(__name__)


# ============================================================================
# 常量定义
# ============================================================================

# 子代理类型描述
SUBAGENT_TYPES = {
    "general": "通用子代理 - 处理一般性任务",
    "explore": "探索子代理 - 用于代码库探索和理解",
    "plan": "规划子代理 - 用于生成实现计划",
    "summary": "摘要子代理 - 用于总结和提炼信息",
}

# 允许子代理使用的工具（只读工具）
ALLOWED_TOOLS = frozenset({
    "list_dir",
    "search_files",
    "search_code",
    "read_file",
    "todo_write",
    "file_info",
})

# 禁止子代理使用的工具（写入和危险操作）
DENIED_TOOLS = frozenset({
    "write_file",
    "edit_file",
    "delete_file",
    "append_file",
    "run_shell",
    "task",  # 防止递归
})

WRITE_TOOLS = frozenset({
    "write_file",
    "append_file",
    "write_file_chunks",
    "append_file_chunks",
    "edit_file",
})


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class SubagentResult:
    """子代理执行结果"""

    success: bool
    content: str
    tool_usage: Dict[str, int]
    steps_taken: int
    subagent_type: str
    model_used: str = "main"
    error: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class TaskResponse:
    """
    Task 工具的统一响应格式
    """

    status: str  # "success" | "error"
    data: Dict[str, Any]
    text: str
    stats: Dict[str, Any]
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "data": self.data,
            "text": self.text,
            "stats": self.stats,
            "context": self.context,
        }

    def to_text(self) -> str:
        """转换为文本格式（用于 LLM 消费）"""
        subagent_type = str(self.data.get("subagent_type", "unknown"))
        lines = [
            f"--- TASK RESULT ---",
            f"状态: {self.status}",
            f"子代理类型: {subagent_type}",
            f"模型: {self.data.get('model_used', 'unknown')}",
            f"执行步数: {self.stats.get('tool_calls', 0)}",
            f"耗时: {self.stats.get('time_ms', 0)}ms",
        ]
        if subagent_type.startswith("team:"):
            lines.append(f"团队成员: {subagent_type.split(':', 1)[1]}")

        tool_summary = self.data.get("tool_summary", [])
        if tool_summary:
            tools_str = ", ".join(f"{t['tool']}={t['count']}" for t in tool_summary)
            lines.append(f"工具使用: {tools_str}")

        lines.append("")
        lines.append("--- 结果 ---")
        lines.append(self.text)

        return "\n".join(lines)


# ============================================================================
# 子代理运行器
# ============================================================================

class SubagentRunner:
    """
    子代理运行器

    运行一个独立的子代理会话，具有：
    - 独立的消息历史
    - 受限的工具访问
    - 循环检测
    - 参数验证
    """

    # 循环检测配置
    MAX_RECENT_CALLS = 5
    LOOP_THRESHOLD = 3  # 连续相同调用次数阈值
    DEFAULT_INLINE_FILE_CHARS = 1800

    def __init__(
        self,
        llm_client: GLMClient,
        tool_registry: ToolRegistry,
        subagent_type: str = "general",
        max_steps: int = 15,
        workspace_dir: Path = None,
        allowed_tools: Optional[set[str]] = None,
        denied_tools: Optional[set[str]] = None,
        system_prompt_override: Optional[str] = None,
    ):
        self.llm = llm_client
        self.subagent_type = subagent_type
        self.max_steps = max_steps
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self.allowed_tools = set(allowed_tools) if allowed_tools else set(ALLOWED_TOOLS)
        if denied_tools is not None:
            self.denied_tools = set(denied_tools)
        elif allowed_tools is not None:
            # 显式传入 allowed_tools 时，避免默认拒绝列表误伤（例如 team-builder 需要写文件工具）。
            self.denied_tools = set()
        else:
            self.denied_tools = set(DENIED_TOOLS)
        self.system_prompt_override = system_prompt_override or ""
        self.max_inline_file_chars = int(
            os.getenv("SUBAGENT_MAX_INLINE_FILE_CHARS", str(self.DEFAULT_INLINE_FILE_CHARS))
        )

        # 创建受限的工具注册器
        self.tool_registry = self._create_filtered_registry(tool_registry)

        # 消息历史
        self.messages: List[Message] = []

        # 工具使用统计
        self.tool_usage: Dict[str, int] = {}

        # 循环检测
        self._recent_calls: List[str] = []
        self._loop_warnings = 0
        self._write_tool_failures = 0
        self._write_failover_injected = False

    def _create_filtered_registry(self, full_registry: ToolRegistry) -> ToolRegistry:
        """创建受限的工具注册器"""
        filtered = ToolRegistry()

        for tool in full_registry.get_all().values():
            tool_name = tool.name
            if tool_name in self.denied_tools:
                continue
            if tool_name in self.allowed_tools:
                filtered.register(tool)

        logger.debug(f"子代理工具过滤: {list(filtered.list_tools())}")
        return filtered

    def run(self, task_description: str, task_prompt: str) -> SubagentResult:
        """运行子代理"""
        if self.system_prompt_override:
            role_prompt = self.system_prompt_override
        else:
            try:
                role_prompt = get_subagent_prompt(self.subagent_type)
            except ValueError as e:
                return SubagentResult(
                    success=False,
                    content=str(e),
                    tool_usage={},
                    steps_taken=0,
                    subagent_type=self.subagent_type,
                    error=str(e),
                )

        system_prompt = f"{role_prompt}\n\n# 当前任务\n{task_description}"
        self.messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=task_prompt),
        ]

        for step in range(self.max_steps):
            try:
                response = self.llm.complete(
                    messages=self.messages,
                    tools=self._get_tools_schemas(),
                )
            except Exception as e:
                logger.error(f"子代理 LLM 调用失败: {e}")
                return SubagentResult(
                    success=False,
                    content=f"LLM 调用失败: {e}",
                    tool_usage=self.tool_usage,
                    steps_taken=step,
                    subagent_type=self.subagent_type,
                    error=str(e),
                )

            self.messages.append(Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            if response.tool_calls:
                if self._detect_loop(response.tool_calls):
                    self._loop_warnings += 1
                    if self._loop_warnings >= 2:
                        logger.warning("子代理检测到循环，强制终止")
                        return SubagentResult(
                            success=False,
                            content="检测到重复的工具调用模式，任务终止",
                            tool_usage=self.tool_usage,
                            steps_taken=step + 1,
                            subagent_type=self.subagent_type,
                            error="循环检测终止",
                        )
                    self.messages.append(Message(
                        role="system",
                        content="警告：检测到重复的工具调用，请尝试其他方法或直接给出答案。"
                    ))

                for tool_call in response.tool_calls:
                    tool_result = self._execute_tool_call(tool_call)
                    self.messages.append(Message(
                        role="tool",
                        content=tool_result,
                        tool_call_id=tool_call.id,
                        name=tool_call.function.name,
                    ))
                    if (
                        not self._write_failover_injected
                        and "写文件工具已连续失败2次" in tool_result
                    ):
                        self._write_failover_injected = True
                        self.messages.append(
                            Message(
                                role="system",
                                content=(
                                    "写文件工具已连续失败2次。立即降级为："
                                    "1) 先用 write_file_chunks 写最小 HTML 骨架；"
                                    "2) 再用 append_file_chunks 按章节追加；"
                                    f"3) 每个 chunk <= {self.max_inline_file_chars} 字符；"
                                    "4) 不要重复同一失败调用。"
                                ),
                            )
                        )
            else:
                logger.info(f"子代理完成，共 {step + 1} 步")
                return SubagentResult(
                    success=True,
                    content=response.content or "",
                    tool_usage=self.tool_usage,
                    steps_taken=step + 1,
                    subagent_type=self.subagent_type,
                )

        return SubagentResult(
            success=False,
            content="达到最大步数限制，任务未完成",
            tool_usage=self.tool_usage,
            steps_taken=self.max_steps,
            subagent_type=self.subagent_type,
            error="达到最大步数",
        )

    def _get_tools_schemas(self) -> List[Dict[str, Any]]:
        return [t.to_openai_schema() for t in self.tool_registry.get_all().values()]

    def _execute_tool_call(self, tool_call) -> str:
        tool_name = tool_call.function.name
        arguments = tool_call.function.arguments
        tool_name, arguments = self._normalize_file_write_call(tool_name, arguments)

        logger.debug(f"子代理执行工具: {tool_name}")

        fixed_args, validation_error = ArgumentValidator.validate_and_fix(
            tool_name, arguments
        )
        if validation_error:
            logger.warning(f"子代理参数验证失败: {validation_error}")
            hint = ArgumentValidator.get_usage_hint(tool_name)
            return self._format_tool_param_error(tool_name, validation_error, hint)

        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

        try:
            result = self.tool_registry.execute(tool_name, **fixed_args)
            result_text = str(result)
            if tool_name in WRITE_TOOLS and self._looks_like_error_result(result_text):
                self._write_tool_failures += 1
            elif tool_name in WRITE_TOOLS:
                self._write_tool_failures = 0
            return result_text
        except Exception as e:
            error_msg = f"工具执行失败: {e}"
            logger.error(error_msg)
            if tool_name in WRITE_TOOLS:
                self._write_tool_failures += 1
            return error_msg

    def _normalize_file_write_call(self, tool_name: str, arguments: Any) -> tuple[str, Any]:
        if tool_name not in {"write_file", "append_file"}:
            return tool_name, arguments
        if not isinstance(arguments, dict):
            return tool_name, arguments

        file_path = arguments.get("file_path")
        content = arguments.get("content")
        if not isinstance(file_path, str) or not file_path.strip():
            return tool_name, arguments
        if not isinstance(content, str) or len(content) <= self.max_inline_file_chars:
            return tool_name, arguments

        chunk_tool = "write_file_chunks" if tool_name == "write_file" else "append_file_chunks"
        chunks = [
            content[i:i + self.max_inline_file_chars]
            for i in range(0, len(content), self.max_inline_file_chars)
        ]
        logger.info(
            "子代理自动转换超长写入: %s -> %s (%s chars, %s chunks)",
            tool_name,
            chunk_tool,
            len(content),
            len(chunks),
        )
        return chunk_tool, {"file_path": file_path, "chunks": chunks}

    def _format_tool_param_error(self, tool_name: str, validation_error: str, hint: str) -> str:
        if tool_name in WRITE_TOOLS:
            self._write_tool_failures += 1
            failover = ""
            if self._write_tool_failures >= 2:
                failover = (
                    f"\n写文件工具已连续失败2次，立即降级："
                    f"先骨架，再 append_file_chunks，每块 <= {self.max_inline_file_chars} 字符。"
                )
            return f"参数错误: {validation_error}\n正确用法: {hint}{failover}"
        return f"参数错误: {validation_error}\n正确用法: {hint}"

    @staticmethod
    def _looks_like_error_result(text: str) -> bool:
        probe = (text or "").lower()
        markers = ("错误", "error", "failed", "traceback", "参数错误")
        return any(marker in probe for marker in markers)

    def _detect_loop(self, tool_calls) -> bool:
        signatures = []
        for tc in tool_calls:
            name = tc.function.name
            args = tc.function.arguments
            args_hash = hashlib.md5(str(args).encode()).hexdigest()[:8]
            signatures.append(f"{name}:{args_hash}")

        current_sig = "|".join(sorted(signatures))
        self._recent_calls.append(current_sig)

        if len(self._recent_calls) > self.MAX_RECENT_CALLS:
            self._recent_calls.pop(0)

        if len(self._recent_calls) >= self.LOOP_THRESHOLD:
            recent = self._recent_calls[-self.LOOP_THRESHOLD:]
            if len(set(recent)) == 1:
                return True

        return False
