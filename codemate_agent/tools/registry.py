"""
工具注册器

管理所有可用工具的注册、查找和执行。
"""

from typing import Optional, List
from codemate_agent.tools.base import Tool


class ToolRegistry:
    """
    工具注册器

    管理所有可用工具。
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        注册工具

        Args:
            tool: 工具实例
        """
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """
        注销工具

        Args:
            name: 工具名称
        """
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[Tool]:
        """
        获取工具

        Args:
            name: 工具名称

        Returns:
            Tool: 工具实例，不存在返回 None
        """
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """
        列出所有工具名称

        Returns:
            List[str]: 工具名称列表
        """
        return list(self._tools.keys())

    def get_all(self) -> dict[str, Tool]:
        """
        获取所有工具

        Returns:
            Dict[str, Tool]: 工具字典
        """
        return self._tools.copy()

    def get_tools_description(self) -> str:
        """
        获取所有工具的描述文本

        Returns:
            str: 格式化的工具描述
        """
        lines = []
        for name, tool in self._tools.items():
            lines.append(f"- {name}: {tool.description}")
        return "\n".join(lines)

    def execute(self, name: str, input: str = None, **kwargs) -> str:
        """
        执行工具

        Args:
            name: 工具名称
            input: 输入参数（通用参数名，会映射到正确的参数名）
            **kwargs: 其他工具参数

        Returns:
            str: 执行结果
        """
        tool = self.get(name)
        if tool is None:
            available = ", ".join(self.list_tools())
            return f"错误: 工具 '{name}' 不存在。可用工具: {available}"

        try:
            # 参数映射：将通用的 'input' 参数映射到正确的参数名
            # 注意：当前工具调用主要通过 **kwargs 传递所有参数
            # 此映射仅用于兼容旧版调用方式（使用 'input' 参数）
            if input is not None:
                # 根据工具名称决定参数名
                param_mapping = {
                    "read_file": "file_path",
                    "write_file": "file_path",  # write_file 的 content 参数通过 kwargs 传递
                    "file_info": "path",
                    "list_dir": "path",
                    "search_code": "pattern",
                    "find_definition": "name",
                    "analyze_project": "path",
                }
                param_name = param_mapping.get(name, "input")
                kwargs[param_name] = input

            # 调试：记录参数
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"执行工具 {name}，参数: {kwargs}")

            return tool.run(**kwargs)
        except Exception as e:
            import traceback
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"工具执行出错 [{name}]: {e}\n{traceback.format_exc()}")
            return f"工具执行出错: {e}"

    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={len(self._tools)})"
