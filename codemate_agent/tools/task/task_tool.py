"""
任务委托工具

TaskTool 作为薄适配层，委托 SubagentRunner 执行子代理任务并格式化输出。
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from codemate_agent.llm.client import LLMClient as GLMClient
from codemate_agent.prompts.agents_prompts import get_default_model
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
    
    def __init__(self, working_dir: str = "."):
        super().__init__()
        self._working_dir = working_dir
        
        # 主模型客户端（运行时注入）
        self._main_llm_client: Optional[GLMClient] = None
        # 轻量模型客户端（运行时注入或与主模型相同）
        self._light_llm_client: Optional[GLMClient] = None
        # 工具注册器
        self._tool_registry: Optional[ToolRegistry] = None
        
        # 摘要缓存
        self._summary_cache: Dict[str, Tuple[str, float]] = {}
    
    def set_dependencies(
        self,
        main_llm_client: GLMClient,
        tool_registry: ToolRegistry,
        light_llm_client: Optional[GLMClient] = None,
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
                    "enum": ["general", "explore", "plan", "summary"],
                    "description": "子代理类型，默认为 general"
                },
                "model": {
                    "type": "string",
                    "enum": ["main", "light"],
                    "description": "模型选择，默认根据类型自动选择"
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
            subagent_type: 子代理类型（可选）
            model: 模型选择（可选）
            
        Returns:
            str: 格式化的结果字符串
        """
        # 检查依赖
        if not self._main_llm_client or not self._tool_registry:
            return self._format_error("INTERNAL_ERROR", "Task 工具未正确初始化（缺少依赖）")
        
        # 提取参数
        description = kwargs.get("description", "")
        prompt = kwargs.get("prompt", "")
        subagent_type = kwargs.get("subagent_type", "general")
        model = kwargs.get("model")
        
        # 参数验证
        validation_error = ArgumentValidator.validate("task", kwargs)
        if validation_error:
            return self._format_error("INVALID_PARAM", validation_error)
        
        # 验证子代理类型
        if subagent_type not in SUBAGENT_TYPES:
            return self._format_error(
                "INVALID_PARAM",
                f"不支持的子代理类型: {subagent_type}。"
                f"支持的类型: {list(SUBAGENT_TYPES.keys())}"
            )
        
        # 确定使用的模型
        if model is None:
            model = get_default_model(subagent_type)
        
        llm_client = self._light_llm_client if model == "light" else self._main_llm_client
        
        # 获取最大步数
        import os
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
