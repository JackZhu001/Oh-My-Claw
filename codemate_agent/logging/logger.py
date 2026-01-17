"""
基础运行时日志 - Rich 美化输出

提供带颜色的终端日志输出，支持动态日志级别。
"""

import logging
import sys
from typing import Optional

try:
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# 默认日志格式
# RichHandler 会自动显示 logger 名称和级别，所以格式简化
DEFAULT_FORMAT = "%(message)s"
# 非 Rich 模式下的完整格式
FULL_FORMAT = "%(name)s - %(levelname)s - %(message)s"

# 全局 logger 缓存
_loggers: dict[str, logging.Logger] = {}


def setup_logger(
    name: str = "codemate",
    level: str = "INFO",
    format_string: Optional[str] = None,
    rich_enabled: bool = True,
) -> logging.Logger:
    """
    设置并返回一个日志记录器

    Args:
        name: logger 名称，建议使用 __name__ 或模块名
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: 自定义格式字符串
        rich_enabled: 是否启用 Rich 美化输出（需要 rich 库）

    Returns:
        配置好的 logger 实例

    Example:
        >>> logger = setup_logger(__name__, level="DEBUG")
        >>> logger.debug("调试信息")
        >>> logger.info("普通信息")
        >>> logger.warning("警告信息")
    """
    # 如果已经创建过，直接返回
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加 handler
    if not logger.handlers:
        if RICH_AVAILABLE and rich_enabled:
            handler = RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_path=True,
                markup=True,  # 支持 [red]红色[/red] 这种标记
            )
            # RichHandler 自动显示 logger 名称和级别
            actual_format = format_string or DEFAULT_FORMAT
        else:
            handler = logging.StreamHandler(sys.stderr)
            # 非 Rich 模式需要完整格式
            actual_format = format_string or FULL_FORMAT

        formatter = logging.Formatter(actual_format)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # 防止日志传播到父 logger
        logger.propagate = False

    _loggers[name] = logger
    return logger


def get_logger(name: str = "codemate") -> logging.Logger:
    """
    获取或创建一个 logger

    这是 setup_logger 的简化版本，使用默认配置。

    Args:
        name: logger 名称

    Returns:
        logger 实例
    """
    if name in _loggers:
        return _loggers[name]
    return setup_logger(name)


def set_global_level(level: str) -> None:
    """
    设置所有 codemate logger 的日志级别

    Args:
        level: 日志级别字符串
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    for logger in _loggers.values():
        logger.setLevel(log_level)


# 预定义的模块 loggers
def get_agent_logger() -> logging.Logger:
    """获取 Agent 模块的 logger"""
    return get_logger("codemate.agent")


def get_llm_logger() -> logging.Logger:
    """获取 LLM 模块的 logger"""
    return get_logger("codemate.llm")


def get_tools_logger() -> logging.Logger:
    """获取 Tools 模块的 logger"""
    return get_logger("codemate.tools")


def get_trace_logger() -> logging.Logger:
    """获取 Trace 模块的 logger"""
    return get_logger("codemate.trace")
