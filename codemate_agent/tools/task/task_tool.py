"""
任务委托工具

TaskTool 作为薄适配层，委托 SubagentRunner 执行子代理任务并格式化输出。
"""

import logging
import hashlib
import os
import re
import time
import uuid
from typing import Any, Callable, Dict, Optional, Tuple

from codemate_agent.llm.client import LLMClient as GLMClient
from codemate_agent.prompts.agents_prompts import get_default_model
from codemate_agent.schema import Message
from codemate_agent.skill import SkillManager
from codemate_agent.team.coordinator import StrictWorkflowError
from codemate_agent.team.definitions import ExecutionResult
from codemate_agent.tools.base import Tool
from codemate_agent.tools.registry import ToolRegistry
from codemate_agent.validation import ArgumentValidator
from codemate_agent.tools.task.subagent_runner import (
    SubagentRunner,
    SubagentResult,
    TaskResponse,
    SUBAGENT_TYPES,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Task 工具
# ============================================================================

class TaskTool(Tool):
    """
    任务委托工具 (MVP 版本)
    
    允许主代理将任务委托给子代理执行。
    
    特性：
    - 支持 main/light 双模型路由
    - 统一响应格式
    - 智能摘要（可选）
    - 参数验证
    """
    
    # 智能摘要配置
    DEFAULT_SUMMARY_THRESHOLD = 1500  # 超过此长度触发摘要
    SUMMARY_CACHE_TTL = 300  # 摘要缓存有效期（秒）
    TEAM_ROLE_SUBAGENT_ALIASES = {
        "researcher": "explore",
        "builder": "general",
        "reviewer": "summary",
        "lead": "plan",
    }
    SKILL_DECLARATION_PATTERNS = (
        r"\[使用\s*Skill[:\s]*([a-zA-Z0-9_-]+)\]",
        r"\[Using\s*Skill[:\s]*([a-zA-Z0-9_-]+)\]",
        r"\[Skill[:\s]*([a-zA-Z0-9_-]+)\]",
    )
    MAX_CONTEXT_SUMMARY_CHARS = 1200
    
    def __init__(self, working_dir: str = "."):
        super().__init__()
        self._working_dir = working_dir
        
        # 主模型客户端（运行时注入）
        self._main_llm_client: Optional[GLMClient] = None
        # 轻量模型客户端（运行时注入或与主模型相同）
        self._light_llm_client: Optional[GLMClient] = None
        # 工具注册器
        self._tool_registry: Optional[ToolRegistry] = None
        self._team_coordinator = None
        self._delegate_handler: Optional[Callable[..., ExecutionResult]] = None
        self._skill_manager = SkillManager()
        
        # 摘要缓存
        self._summary_cache: Dict[str, Tuple[str, float]] = {}
    
    def set_dependencies(
        self,
        main_llm_client: GLMClient,
        tool_registry: ToolRegistry,
        light_llm_client: Optional[GLMClient] = None,
        team_coordinator=None,
        delegate_handler: Optional[Callable[..., ExecutionResult]] = None,
    ):
        """
        设置依赖（由 Agent 注入）
        
        Args:
            main_llm_client: 主模型客户端
            tool_registry: 工具注册器
            light_llm_client: 轻量模型客户端（可选，默认使用主模型）
        """
        self._main_llm_client = main_llm_client
        self._light_llm_client = light_llm_client or main_llm_client
        self._tool_registry = tool_registry
        self._team_coordinator = team_coordinator
        self._delegate_handler = delegate_handler

    def set_delegate_handler(self, handler: Optional[Callable[..., ExecutionResult]]) -> None:
        self._delegate_handler = handler
    
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
- summary: 总结和提炼信息

【模型选择】
- main: 主模型，用于复杂推理任务
- light: 轻量模型，用于简单任务（默认根据类型自动选择）

参数：
- description: 任务简述（必填，如 "分析项目结构"）
- prompt: 详细任务指令（必填，描述具体要做什么）
- subagent_type: 子代理类型（可选，默认: general）
- model: 模型选择（可选，默认: 根据类型自动选择）

返回：
- 任务执行结果
- 工具使用统计
- 执行步数和耗时"""
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "任务简述，如 '分析项目结构'"
                },
                "prompt": {
                    "type": "string",
                    "description": "详细任务指令，描述具体要做什么"
                },
                "subagent_type": {
                    "type": "string",
                    "enum": [
                        "general",
                        "explore",
                        "plan",
                        "summary",
                        "researcher",
                        "builder",
                        "reviewer",
                        "lead",
                    ],
                    "description": "子代理类型，默认为 general"
                },
                "model": {
                    "type": "string",
                    "enum": ["main", "light"],
                    "description": "模型选择，默认根据类型自动选择"
                },
                "agent_id": {
                    "type": "string",
                    "description": "指定团队成员（可选，如 researcher/builder/reviewer/lead）",
                },
                "context_summary": {
                    "type": "string",
                    "description": "补充上下文摘要（可选）",
                },
                "skill_context": {
                    "type": "string",
                    "description": "补充 skill 上下文（可选）",
                },
                "skill_name": {
                    "type": "string",
                    "description": "指定关联的 skill 名称（可选）",
                },
            },
            "required": ["description", "prompt"]
        }
    
    def run(self, **kwargs) -> str:
        """
        执行任务委托
        
        Args:
            description: 任务简述
            prompt: 详细任务指令
            subagent_type: 子代理类型（可选）
            model: 模型选择（可选）
            
        Returns:
            str: 格式化的结果字符串
        """
        # 检查依赖
        if self._main_llm_client is None or self._tool_registry is None:
            return self._format_error("INTERNAL_ERROR", "Task 工具未正确初始化（缺少依赖）")
        
        # 提取参数
        description = kwargs.get("description", "")
        prompt = kwargs.get("prompt", "")
        raw_subagent_type = (kwargs.get("subagent_type", "general") or "general").strip().lower()
        subagent_type = self._normalize_subagent_type(raw_subagent_type)
        model = kwargs.get("model")
        requested_agent_id = (kwargs.get("agent_id") or "").strip()
        
        # 参数验证
        validation_error = ArgumentValidator.validate("task", kwargs)
        if validation_error:
            return self._format_error("INVALID_PARAM", validation_error)
        
        # 验证子代理类型
        if subagent_type not in SUBAGENT_TYPES:
            supported = list(SUBAGENT_TYPES.keys()) + list(self.TEAM_ROLE_SUBAGENT_ALIASES.keys())
            return self._format_error(
                "INVALID_PARAM",
                f"不支持的子代理类型: {raw_subagent_type}。"
                f"支持的类型: {supported}"
            )

        if self._delegate_handler is not None or self._team_coordinator is not None:
            strict_mode = self._is_team_strict_mode_enabled()
            if strict_mode and not requested_agent_id:
                return self._format_error(
                    "TEAM_STRICT_VIOLATION",
                    "TEAM_STRICT_MODE 约束：使用 task 进行团队委托时必须显式传入 agent_id "
                    "(researcher/builder/reviewer/lead)，禁止仅靠 subagent_type 隐式路由。",
                )
            target_agent = requested_agent_id or self._map_subagent_to_member(raw_subagent_type)
            context_summary = self._build_delegation_context(
                description=description,
                prompt=prompt,
                raw_subagent_type=raw_subagent_type,
                target_agent=target_agent,
                kwargs=kwargs,
            )
            try:
                start_time = time.time()
                if self._delegate_handler is not None:
                    delegated_result = self._delegate_handler(
                        agent_id=target_agent,
                        title=description,
                        instructions=prompt,
                        context_summary=context_summary,
                        cwd=self._working_dir,
                    )
                else:
                    delegated_result = self._team_coordinator.dispatch_to(
                        agent_id=target_agent,
                        title=description,
                        instructions=prompt,
                        context_summary=context_summary,
                        delegated_by="lead",
                        cwd=self._working_dir,
                    )
                duration_ms = int((time.time() - start_time) * 1000)
                return self._format_delegated_success(
                    delegated_result=delegated_result,
                    duration_ms=duration_ms,
                    params_input=kwargs,
                    member=target_agent,
                )
            except StrictWorkflowError as e:
                return self._format_error("TEAM_STRICT_VIOLATION", str(e))
            except Exception as e:
                logger.error("团队调度失败: %s", e)
                return self._format_error("TEAM_DISPATCH_ERROR", str(e))
        
        # 确定使用的模型
        if model is None:
            model = get_default_model(subagent_type)
        
        llm_client = self._light_llm_client if model == "light" else self._main_llm_client
        
        # 获取最大步数
        max_steps = int(os.getenv("SUBAGENT_MAX_STEPS", "15"))
        
        # 创建并运行子代理
        start_time = time.time()
        session_id = str(uuid.uuid4())[:8]
        
        logger.info(f"启动子代理 [{session_id}]: type={subagent_type}, model={model}")
        
        try:
            runner = SubagentRunner(
                llm_client=llm_client,
                tool_registry=self._tool_registry,
                subagent_type=subagent_type,
                max_steps=max_steps,
                workspace_dir=self._working_dir,
            )
            
            result = runner.run(description, prompt)
            result.model_used = model
            
        except Exception as e:
            logger.error(f"子代理执行失败: {e}")
            return self._format_error("INTERNAL_ERROR", str(e))
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 格式化响应
        return self._format_success(result, duration_ms, kwargs)

    def _format_delegated_success(
        self,
        *,
        delegated_result: ExecutionResult,
        duration_ms: int,
        params_input: Dict[str, Any],
        member: str,
    ) -> str:
        content = delegated_result.summary or "No summary returned."
        if len(content) > self.DEFAULT_SUMMARY_THRESHOLD:
            content = self._truncate_content(content)
        response = TaskResponse(
            status="success" if delegated_result.success else "error",
            data={
                "status": delegated_result.status,
                "result": content,
                "tool_summary": [
                    {"tool": tool, "count": count}
                    for tool, count in delegated_result.tool_usage.items()
                ],
                "model_used": member,
                "subagent_type": f"team:{member}",
                "artifact_paths": delegated_result.artifact_paths,
                "artifact_manifest_path": delegated_result.artifact_manifest_path,
                "session_id": delegated_result.session_id,
            },
            text=content,
            stats={
                "time_ms": duration_ms,
                "tool_calls": sum(delegated_result.tool_usage.values()),
                "steps": 0,
                "model": member,
            },
            context={
                "cwd": str(self._working_dir),
                "params_input": params_input,
                "error": delegated_result.error,
            },
        )
        return response.to_text()
    
    def _format_success(
        self,
        result: SubagentResult,
        duration_ms: int,
        params_input: Dict[str, Any],
    ) -> str:
        """格式化成功响应"""
        # 处理内容：可选智能摘要
        content = result.content
        content_length = len(content)
        
        if content_length > self.DEFAULT_SUMMARY_THRESHOLD:
            summary = self._generate_intelligent_summary(content, result.subagent_type)
            if summary:
                content = summary
                logger.info(f"子代理结果已摘要: {content_length} → {len(summary)} 字符")
            else:
                # 摘要失败，使用结构化截断
                content = self._truncate_content(content)
        
        # 构建工具使用统计
        tool_summary = [
            {"tool": tool, "count": count}
            for tool, count in result.tool_usage.items()
        ]
        
        # 构建响应
        response = TaskResponse(
            status="success" if result.success else "error",
            data={
                "status": "completed" if result.success else "failed",
                "result": content,
                "tool_summary": tool_summary,
                "model_used": result.model_used,
                "subagent_type": result.subagent_type,
            },
            text=content,
            stats={
                "time_ms": duration_ms,
                "tool_calls": sum(result.tool_usage.values()),
                "steps": result.steps_taken,
                "model": result.model_used,
            },
            context={
                "cwd": str(self._working_dir),
                "params_input": params_input,
            },
        )
        
        return response.to_text()
    
    def _format_error(self, error_code: str, message: str) -> str:
        """格式化错误响应"""
        response = TaskResponse(
            status="error",
            data={
                "error_code": error_code,
                "message": message,
            },
            text=f"错误 [{error_code}]: {message}",
            stats={},
            context={},
        )
        return response.to_text()
    
    def _truncate_content(self, content: str) -> str:
        """结构化截断内容"""
        max_length = 2000
        if len(content) <= max_length:
            return content
        
        # 保留开头和结尾
        head_length = int(max_length * 0.6)
        tail_length = int(max_length * 0.3)
        
        head = content[:head_length]
        tail = content[-tail_length:]
        
        omitted = len(content) - head_length - tail_length
        return f"{head}\n\n... [省略 {omitted} 字符] ...\n\n{tail}"
    
    def _generate_intelligent_summary(
        self,
        content: str,
        subagent_type: str,
    ) -> Optional[str]:
        """
        生成智能摘要
        
        成本控制策略：
        1. 内容哈希缓存
        2. 最大输入长度限制
        """
        if not self._light_llm_client:
            return None
        
        # 计算内容哈希
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        
        # 检查缓存
        current_time = time.time()
        if content_hash in self._summary_cache:
            cached_summary, cache_time = self._summary_cache[content_hash]
            if current_time - cache_time < self.SUMMARY_CACHE_TTL:
                logger.debug(f"使用缓存的摘要: {content_hash}")
                return cached_summary
        
        # 限制输入长度
        max_input_length = 4000
        truncated_content = content[:max_input_length]
        if len(content) > max_input_length:
            truncated_content += "\n...(后续内容省略)"
        
        # 摘要提示词
        prompt = f"""请将以下{subagent_type}子代理的执行结果摘要为简洁的要点。

要求：
1. 提取关键发现和结论
2. 列出主要操作结果
3. 省略中间过程
4. 使用 Markdown 格式
5. 控制在 300 字以内

原始结果：
{truncated_content}

请生成摘要："""
        
        try:
            response = self._light_llm_client.complete(
                messages=[Message(role="user", content=prompt)],
                tools=None,
            )
            
            summary = response.content.strip() if response.content else None
            
            if summary and len(summary) < len(content):
                # 缓存结果
                self._summary_cache[content_hash] = (summary, current_time)
                
                # 清理过期缓存
                self._cleanup_cache(current_time)
                
                return summary
        
        except Exception as e:
            logger.warning(f"智能摘要生成失败: {e}")
        
        return None
    
    def _cleanup_cache(self, current_time: float) -> None:
        """清理过期缓存"""
        expired = [
            key for key, (_, ts) in self._summary_cache.items()
            if current_time - ts > self.SUMMARY_CACHE_TTL
        ]
        for key in expired:
            del self._summary_cache[key]

    def _map_subagent_to_member(self, subagent_type: str) -> str:
        normalized = (subagent_type or "general").strip().lower()
        if normalized in self.TEAM_ROLE_SUBAGENT_ALIASES:
            return normalized
        if normalized == "explore":
            return "researcher"
        if normalized == "summary":
            return "reviewer"
        if normalized == "plan":
            return "lead"
        return "builder"

    def _normalize_subagent_type(self, subagent_type: str) -> str:
        normalized = (subagent_type or "general").strip().lower()
        if normalized in SUBAGENT_TYPES:
            return normalized
        return self.TEAM_ROLE_SUBAGENT_ALIASES.get(normalized, normalized)

    @staticmethod
    def _is_team_strict_mode_enabled() -> bool:
        return os.getenv("TEAM_STRICT_MODE", "false").strip().lower() == "true"

    def _build_delegation_context(
        self,
        *,
        description: str,
        prompt: str,
        raw_subagent_type: str,
        target_agent: str,
        kwargs: Dict[str, Any],
    ) -> str:
        sections: list[str] = []
        user_context_summary = (kwargs.get("context_summary") or "").strip()
        if user_context_summary:
            sections.append(user_context_summary)

        skill_context = (kwargs.get("skill_context") or "").strip()
        if skill_context:
            sections.append(f"Skill context:\n{skill_context}")

        skill_name = self._resolve_skill_name(description=description, prompt=prompt, kwargs=kwargs)
        if skill_name:
            sections.append(
                "Detected skill hint:\n"
                f"- {skill_name}\n"
                "- Delegatee should call skill tool to load full guidance before implementation."
            )

        sections.append(
            "Delegation metadata:\n"
            f"- target_agent: {target_agent}\n"
            f"- requested_subagent_type: {(raw_subagent_type or 'general').strip().lower() or 'general'}"
        )

        combined = "\n\n".join(part for part in sections if part).strip()
        if len(combined) <= self.MAX_CONTEXT_SUMMARY_CHARS:
            return combined
        return combined[: self.MAX_CONTEXT_SUMMARY_CHARS].rstrip() + "\n...(truncated)"

    def _resolve_skill_name(self, *, description: str, prompt: str, kwargs: Dict[str, Any]) -> str:
        explicit = (kwargs.get("skill_name") or "").strip()
        if explicit:
            return explicit

        stripped_prompt = (prompt or "").strip()
        if stripped_prompt.startswith("/"):
            maybe = stripped_prompt[1:].split(maxsplit=1)[0].strip()
            if maybe and self._skill_manager.skill_exists(maybe):
                return maybe

        declared = self._extract_declared_skill(stripped_prompt)
        if declared:
            return declared

        candidate = self._skill_manager.match_skill_by_keywords(f"{description}\n{prompt}")
        if candidate and self._skill_manager.skill_exists(candidate):
            return candidate
        return ""

    def _extract_declared_skill(self, content: str) -> str:
        for pattern in self.SKILL_DECLARATION_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if not match:
                continue
            skill_name = match.group(1).strip()
            if skill_name and self._skill_manager.skill_exists(skill_name):
                return skill_name
        return ""
