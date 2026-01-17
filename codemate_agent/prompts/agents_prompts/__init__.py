"""
子代理 Prompt 模块

按类型管理子代理的系统提示词。
"""

from .subagent_general_prompt import SUBAGENT_GENERAL_PROMPT
from .subagent_explore_prompt import SUBAGENT_EXPLORE_PROMPT
from .subagent_plan_prompt import SUBAGENT_PLAN_PROMPT
from .subagent_summary_prompt import SUBAGENT_SUMMARY_PROMPT

# 类型到 Prompt 的映射
SUBAGENT_PROMPTS = {
    "general": SUBAGENT_GENERAL_PROMPT,
    "explore": SUBAGENT_EXPLORE_PROMPT,
    "plan": SUBAGENT_PLAN_PROMPT,
    "summary": SUBAGENT_SUMMARY_PROMPT,
}

# 类型到默认模型的映射
SUBAGENT_MODEL_DEFAULTS = {
    "explore": "light",   # 探索通常简单
    "summary": "light",   # 摘要不需要强推理
    "plan": "main",       # 规划需要复杂推理
    "general": "main",    # 通用任务用主模型
}


def get_subagent_prompt(subagent_type: str) -> str:
    """
    获取子代理的系统提示词
    
    Args:
        subagent_type: 子代理类型
        
    Returns:
        对应的系统提示词
        
    Raises:
        ValueError: 如果类型不支持
    """
    if subagent_type not in SUBAGENT_PROMPTS:
        raise ValueError(
            f"不支持的子代理类型: {subagent_type}。"
            f"支持的类型: {list(SUBAGENT_PROMPTS.keys())}"
        )
    return SUBAGENT_PROMPTS[subagent_type]


def get_default_model(subagent_type: str) -> str:
    """
    获取子代理类型的默认模型
    
    Args:
        subagent_type: 子代理类型
        
    Returns:
        默认模型名称 ("main" 或 "light")
    """
    return SUBAGENT_MODEL_DEFAULTS.get(subagent_type, "main")


__all__ = [
    "SUBAGENT_GENERAL_PROMPT",
    "SUBAGENT_EXPLORE_PROMPT",
    "SUBAGENT_PLAN_PROMPT",
    "SUBAGENT_SUMMARY_PROMPT",
    "SUBAGENT_PROMPTS",
    "SUBAGENT_MODEL_DEFAULTS",
    "get_subagent_prompt",
    "get_default_model",
]
