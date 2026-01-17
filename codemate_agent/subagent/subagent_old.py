"""
子代理系统

支持将任务委托给专门的子代理执行。
"""

import json
import logging
import time
import uuid
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

from codemate_agent.llm.client import GLMClient
from codemate_agent.schema import Message, LLMResponse
from codemate_agent.tools.base import Tool
from codemate_agent.tools.registry import ToolRegistry


logger = logging.getLogger(__name__)


# 子代理类型
SUBAGENT_TYPES = {
    "general": "通用子代理 - 处理一般性任务",
    "explore": "探索子代理 - 用于代码库探索和理解",
    "plan": "规划子代理 - 用于生成实现计划",
}

# 子代理工具限制：只读工具
ALLOWED_TOOLS = frozenset({
    "list_dir", "search_files", "search_code",
    "read_file", "todo_write",
})

# 禁止子代理使用的工具
DENIED_TOOLS = frozenset({
    "write_file", "edit_file", "delete_file", "append_file", "run_shell", "task",
})


@dataclass
class SubagentResult:
    """子代理执行结果"""
    success: bool
    content: str
    tool_usage: Dict[str, int]
    steps_taken: int
    subagent_type: str
    error: Optional[str] = None
    summary: Optional[str] = None  # 智能摘要（如果有）


class SubagentRunner:
    """
    子代理运行器

    运行一个独立的子代理会话，具有：
    - 独立的消息历史
    - 受限的工具访问
    - 最大步数限制
    """

    # 系统提示词模板
    SYSTEM_PROMPTS = {
        "general": """你是通用子代理，负责处理主代理委托的任务。

你的职责：
- 仔细分析任务需求
- 使用可用工具收集信息
- 给出清晰、准确的答案

限制：
- 只使用提供的只读工具
- 不要尝试修改文件
- 返回简洁的结果""",

        "explore": """你是代码探索子代理，负责探索和理解代码库。

你的职责：
- 探索项目结构
- 查找相关文件和代码
- 理解代码关系和依赖

探索策略：
1. 从项目根目录开始，了解整体结构
2. 使用 search_files 查找相关文件
3. 使用 search_code 搜索关键代码
4. 使用 read_file 阅读关键文件
5. 总结发现

限制：
- 只使用只读工具（list_dir, search_files, search_code, read_file）
- 不要创建或修改文件""",

        "plan": """你是规划子代理，负责生成实现计划。

你的职责：
1. 理解任务需求
2. 探索相关代码了解现有模式
3. 设计实现步骤

输出格式：
- 清晰的步骤列表
- 每个步骤说明具体要做什么
- 标注关键文件和依赖关系

限制：
- 只使用只读工具
- 不要实际修改代码
- 计划要具体可执行""",
    }

    def __init__(
        self,
        llm_client: GLMClient,
        tool_registry: ToolRegistry,
        subagent_type: str = "general",
        max_steps: int = 15,
        workspace_dir: Path = None,
    ):
        """
        初始化子代理运行器

        Args:
            llm_client: LLM 客户端
            tool_registry: 工具注册器（会被过滤）
            subagent_type: 子代理类型
            max_steps: 最大执行步数
            workspace_dir: 工作目录
        """
        self.llm = llm_client
        self.subagent_type = subagent_type
        self.max_steps = max_steps
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()

        # 创建受限的工具注册器
        self.tool_registry = self._create_filtered_registry(tool_registry)

        # 消息历史
        self.messages: List[Message] = []

        # 工具使用统计
        self.tool_usage: Dict[str, int] = {}

    def _create_filtered_registry(self, full_registry: ToolRegistry) -> ToolRegistry:
        """创建受限的工具注册器"""
        filtered = ToolRegistry()

        for tool in full_registry.get_all().values():
            tool_name = tool.name

            # 检查是否允许
            if tool_name in DENIED_TOOLS:
                continue

            # 只读工具可以访问
            if tool_name in ALLOWED_TOOLS:
                filtered.register(tool)

        return filtered

    def run(self, task_description: str, task_prompt: str) -> SubagentResult:
        """
        运行子代理

        Args:
            task_description: 任务简述
            task_prompt: 详细任务指令

        Returns:
            SubagentResult: 执行结果
        """
        # 构建系统提示词
        system_prompt = self.SYSTEM_PROMPTS.get(
            self.subagent_type,
            self.SYSTEM_PROMPTS["general"]
        )
        system_prompt = f"{system_prompt}\n\n# 当前任务\n{task_description}"

        # 初始化消息
        self.messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=task_prompt),
        ]

        # 主循环
        for step in range(self.max_steps):
            # 调用 LLM
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

            # 添加助手响应
            self.messages.append(Message(
                role="assistant",
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            # 检查是否有工具调用
            if response.tool_calls:
                # 执行所有工具调用
                for tool_call in response.tool_calls:
                    tool_result = self._execute_tool_call(tool_call)

                    self.messages.append(Message(
                        role="tool",
                        content=tool_result,
                        tool_call_id=tool_call.id,
                        name=tool_call.function.name,
                    ))
            else:
                # 没有工具调用，任务完成
                logger.info(f"子代理完成，共 {step + 1} 步")
                return SubagentResult(
                    success=True,
                    content=response.content or "",
                    tool_usage=self.tool_usage,
                    steps_taken=step + 1,
                    subagent_type=self.subagent_type,
                )

        # 达到最大步数
        return SubagentResult(
            success=False,
            content="达到最大步数限制，任务未完成",
            tool_usage=self.tool_usage,
            steps_taken=self.max_steps,
            subagent_type=self.subagent_type,
            error="达到最大步数",
        )

    def _get_tools_schemas(self) -> List[Dict[str, Any]]:
        """获取工具的 OpenAI Schema 格式"""
        return [t.to_openai_schema() for t in self.tool_registry.get_all().values()]

    def _execute_tool_call(self, tool_call) -> str:
        """执行单个工具调用"""
        tool_name = tool_call.function.name
        arguments = tool_call.function.arguments

        logger.debug(f"子代理执行工具: {tool_name}")

        # 统计工具使用
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

        try:
            result = self.tool_registry.execute(tool_name, **arguments)
            return str(result)
        except Exception as e:
            error_msg = f"工具执行失败: {e}"
            logger.error(error_msg)
            return error_msg


class TaskTool(Tool):
    """
    任务委托工具

    允许主代理将任务委托给子代理。
    """

    # 智能摘要配置
    DEFAULT_SUMMARY_THRESHOLD = 1500  # 超过此长度触发摘要
    MAX_SUMMARY_TOKENS = 500  # 摘要最大 token 数
    SUMMARY_CACHE_TTL = 300  # 摘要缓存有效期（秒）

    def __init__(self, working_dir: str = "."):
        super().__init__()
        self._working_dir = working_dir

        # 这些会在运行时注入
        self._llm_client = None
        self._tool_registry = None

        # 摘要缓存（用于去重，减少 API 调用）
        self._summary_cache: Dict[str, tuple[str, float]] = {}  # content_hash -> (summary, timestamp)

    def set_dependencies(self, llm_client: GLMClient, tool_registry: ToolRegistry):
        """设置依赖（由 Agent 注入）"""
        self._llm_client = llm_client
        self._tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "task"

    @property
    def description(self) -> str:
        return """将任务委托给子代理处理。

【什么时候使用子代理】
- 需要多步探索（如：遍历目录、查找相关文件、分析项目结构）
- 不确定需要多少次工具调用才能完成
- 主要是信息收集和分析，不需要实时反馈
- 可能产生大量中间结果（使用子代理避免占用主对话上下文）

【什么时候直接处理】
- 单次工具调用就能完成（如：读取单个文件）
- 需要实时反馈给用户的操作
- 简单操作（1-2 步内完成）

【子代理类型说明】
- general: 通用任务处理
- explore: 代码探索、文件搜索（推荐用于探索项目结构）
- plan: 生成实现计划

参数：
- description: 任务简述（必填）
- prompt: 详细任务指令（必填，建议详细描述任务要求）
- subagent_type: 子代理类型（可选，默认: general）

返回：
- 任务执行结果
- 工具使用统计
- 执行步数"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "任务简述"
                },
                "prompt": {
                    "type": "string",
                    "description": "详细任务指令"
                },
                "subagent_type": {
                    "type": "string",
                    "enum": ["general", "explore", "plan"],
                    "description": "子代理类型"
                }
            },
            "required": ["description", "prompt"]
        }

    def run(self, **kwargs) -> str:
        """
        执行任务委托

        Args:
            description: 任务简述
            prompt: 详细任务指令
            subagent_type: 子代理类型

        Returns:
            str: 格式化的结果字符串
        """
        if not self._llm_client or not self._tool_registry:
            return "错误: Task 工具未正确初始化（缺少依赖）"

        description = kwargs.get("description", "")
        prompt = kwargs.get("prompt", "")
        subagent_type = kwargs.get("subagent_type", "general")

        # 验证参数
        if not description:
            return "错误: description 参数不能为空"
        if not prompt:
            return "错误: prompt 参数不能为空"

        # 验证子代理类型
        if subagent_type not in SUBAGENT_TYPES:
            subagent_type = "general"

        # 获取最大步数
        import os
        max_steps = int(os.getenv("SUBAGENT_MAX_STEPS", "15"))

        # 创建并运行子代理
        start_time = time.time()

        try:
            runner = SubagentRunner(
                llm_client=self._llm_client,
                tool_registry=self._tool_registry,
                subagent_type=subagent_type,
                max_steps=max_steps,
                workspace_dir=self._working_dir,
            )

            result = runner.run(description, prompt)

        except Exception as e:
            logger.error(f"子代理执行失败: {e}")
            return f"子代理执行失败: {e}"

        duration_ms = int((time.time() - start_time) * 1000)

        # 格式化结果
        return self._format_result(result, duration_ms)

    def _format_result(self, result: SubagentResult, duration_ms: int) -> str:
        """格式化子代理结果"""
        lines = [
            "--- TASK RESULT ---",
            f"子代理类型: {result.subagent_type}",
            f"执行状态: {'成功' if result.success else '失败'}",
            f"执行步数: {result.steps_taken}",
            f"耗时: {duration_ms}ms",
        ]

        if result.tool_usage:
            lines.append(f"工具使用: {', '.join(f'{k}={v}' for k, v in result.tool_usage.items())}")

        lines.append("")
        lines.append("--- 结果 ---")

        # 处理内容：优先使用智能摘要
        content = result.content
        content_length = len(content)

        # 检查是否需要智能摘要
        use_summary = False
        if result.summary:
            # 如果已有摘要（从缓存或新生成）
            content = result.summary
            use_summary = True
        elif content_length > self.DEFAULT_SUMMARY_THRESHOLD:
            # 尝试生成智能摘要
            summary = self._generate_intelligent_summary(content, result.subagent_type)
            if summary:
                content = summary
                use_summary = True
                logger.info(f"子代理结果已智能摘要: {content_length} → {len(summary)} 字符")
            else:
                # 摘要失败，使用截断方式
                content = content[:2000]
                content += f"\n...(内容已截断，原 {content_length} 字符)"
                logger.info(f"子代理结果已截断: {content_length} → 2000 字符")

        lines.append(content)

        if use_summary and content_length > self.DEFAULT_SUMMARY_THRESHOLD:
            lines.append(f"\n[原始内容 {content_length} 字符已摘要为 {len(content)} 字符]")

        return "\n".join(lines)

    def _generate_intelligent_summary(self, content: str, subagent_type: str) -> Optional[str]:
        """
        生成智能摘要

        成本控制策略：
        1. 内容哈希缓存（相同内容不重复摘要）
        2. 最大 token 限制
        3. 超时保护

        Args:
            content: 原始内容
            subagent_type: 子代理类型

        Returns:
            摘要内容，失败返回 None
        """
        if not self._llm_client:
            return None

        # 计算内容哈希用于缓存
        import hashlib
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]

        # 检查缓存
        current_time = time.time()
        if content_hash in self._summary_cache:
            cached_summary, cache_time = self._summary_cache[content_hash]
            if current_time - cache_time < self.SUMMARY_CACHE_TTL:
                logger.debug(f"使用缓存的摘要: {content_hash}")
                return cached_summary

        # 限制输入长度（成本控制）
        max_input_length = 4000  # 约相当于 1300 tokens
        truncated_content = content[:max_input_length]
        if len(content) > max_input_length:
            truncated_content += "\n...(后续内容省略)"

        # 摘要提示词
        prompt = f"""请将以下{subagent_type}子代理的执行结果摘要为简洁的要点。

要求：
1. 提取关键发现和结论
2. 列出主要操作（如果有）
3. 省略中间过程
4. 使用 Markdown 格式
5. 控制在 300 字以内

原始结果：
{truncated_content}

请生成摘要："""

        try:
            response = self._llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
                tools=None,
            )

            summary = response.content.strip() if response.content else None

            if summary and len(summary) < len(content):
                # 缓存结果
                self._summary_cache[content_hash] = (summary, current_time)

                # 清理过期缓存
                self._cleanup_summary_cache(current_time)

                return summary

        except Exception as e:
            logger.warning(f"智能摘要生成失败: {e}")

        return None

    def _cleanup_summary_cache(self, current_time: float) -> None:
        """清理过期的摘要缓存"""
        expired_keys = [
            key for key, (_, timestamp) in self._summary_cache.items()
            if current_time - timestamp > self.SUMMARY_CACHE_TTL
        ]
        for key in expired_keys:
            del self._summary_cache[key]
