"""
工具输出截断器

防止单个工具输出过大导致上下文爆炸。
"""

from typing import Optional


class ObservationTruncator:
    """
    工具输出截断器

    对工具执行结果进行截断，防止单个工具输出占用过多 token。
    """

    # 默认限制
    DEFAULT_MAX_LINES = 2000
    DEFAULT_MAX_BYTES = 51200  # 50KB

    def __init__(
        self,
        max_lines: int = DEFAULT_MAX_LINES,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ):
        """
        初始化截断器

        Args:
            max_lines: 最大行数
            max_bytes: 最大字节数
        """
        self.max_lines = max_lines
        self.max_bytes = max_bytes

    def truncate(self, content: str, tool_name: str = "") -> str:
        """
        截断工具输出

        Args:
            content: 工具输出内容
            tool_name: 工具名称（用于日志）

        Returns:
            截断后的内容
        """
        if not content:
            return content

        original_length = len(content)

        # 按行数截断
        if self.max_lines > 0:
            lines = content.split("\n")
            if len(lines) > self.max_lines:
                content = "\n".join(lines[:self.max_lines])
                content += f"\n... (省略 {len(lines) - self.max_lines} 行)"

        # 按字节数截断
        if self.max_bytes > 0:
            content_bytes = content.encode("utf-8")
            if len(content_bytes) > self.max_bytes:
                # 估算字符截断位置（UTF-8 下英文 1 字节，中文 3 字节）
                max_chars = self.max_bytes // 2
                content = content[:max_chars]
                content += f"... (输出过长，已截断)"

        # 记录截断信息
        if len(content) < original_length:
            truncated_ratio = 1 - (len(content) / original_length)
            return f"[工具输出已截断 {truncated_ratio:.0%}]\n{content}"

        return content

    def should_skip_truncation(self, tool_name: str) -> bool:
        """
        判断是否跳过截断

        某些工具的输出可能不适合截断。

        Args:
            tool_name: 工具名称

        Returns:
            是否跳过截断
        """
        # 这些工具的输出通常较小或需要完整保留
        no_truncate_tools = {
            "ask_user",
            "confirm",
            "get_input",
        }
        return tool_name in no_truncate_tools


# 全局默认截断器
_default_truncator: Optional[ObservationTruncator] = None


def get_truncator() -> ObservationTruncator:
    """获取默认截断器"""
    global _default_truncator
    if _default_truncator is None:
        _default_truncator = ObservationTruncator()
    return _default_truncator
