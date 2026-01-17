"""
工具基类

定义所有工具的抽象接口和 OpenAI Function Calling Schema 支持。

设计思路：
1. 所有工具继承自 Tool 基类
2. 实现必需的属性：name, description, parameters
3. 实现 run() 方法定义工具的具体行为
4. 基类提供 to_openai_schema() 自动生成符合标准的工具定义

使用示例：
    class ReadFile(Tool):
        @property
        def name(self) -> str:
            return "read_file"

        @property
        def description(self) -> str:
            return "读取文件内容"

        @property
        def parameters(self) -> Dict[str, Any]:
            return {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径"
                    }
                },
                "required": ["file_path"]
            }

        def run(self, file_path: str) -> str:
            with open(file_path) as f:
                return f.read()
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from codemate_agent.schema import ToolResult, ToolSchema


class Tool(ABC):
    """
    工具基类

    所有工具都应继承此类并实现相应方法。

    抽象方法（必须实现）：
    - name: 工具名称
    - description: 工具描述
    - run: 工具执行逻辑

    可选方法：
    - parameters: 定义工具参数（默认为空）
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        工具名称

        Agent 通过此名称调用工具。
        名称应该简洁且具有描述性，如 "read_file", "search_code"。

        Returns:
            str: 工具名称
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        工具描述

        描述工具的功能和使用方法，供 LLM 理解。
        好的描述应该包含：
        - 工具的功能
        - 何时使用此工具
        - 参数说明

        示例：
            "读取指定路径的文件内容，返回完整的文件文本。
             用于查看源代码文件、配置文件等。"

        Returns:
            str: 工具描述
        """
        pass

    @property
    def parameters(self) -> Dict[str, Any]:
        """
        工具参数 Schema (JSON Schema 格式)

        定义工具的输入参数，LLM 根据此定义知道如何调用工具。

        JSON Schema 结构：
        {
            "type": "object",              # 固定为 object
            "properties": {                # 参数定义
                "param_name": {            # 参数名
                    "type": "string",      # 参数类型
                    "description": "..."   # 参数描述
                }
            },
            "required": ["param_name"]     # 必填参数列表
        }

        默认返回空对象，子类可重写以定义具体参数。

        Returns:
            Dict: JSON Schema 格式的参数定义
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    @abstractmethod
    def run(self, **kwargs) -> str:
        """
        执行工具

        这是工具的核心方法，定义工具的具体行为。

        Args:
            **kwargs: 工具参数（根据 parameters 定义传入）

        Returns:
            str: 执行结果（必须是字符串形式）

        注意：
        - 返回值会被发送给 LLM
        - 如果执行失败，可以返回包含错误信息的字符串
        - LLM 会根据返回结果决定下一步操作

        示例：
            def run(self, file_path: str) -> str:
                try:
                    with open(file_path) as f:
                        return f.read()
                except FileNotFoundError:
                    return f"错误：文件 {file_path} 不存在"
        """
        pass

    def to_openai_schema(self) -> Dict[str, Any]:
        """
        转换为 OpenAI Function Calling Schema

        将工具定义转换为 OpenAI 兼容的格式。
        这个格式会被发送给 LLM，让 LLM 知道如何调用工具。

        OpenAI Function Calling 格式：
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {...},
                    "required": [...]
                }
            }
        }

        Returns:
            Dict: 符合 OpenAI 标准的工具 schema
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def to_anthropic_schema(self) -> Dict[str, Any]:
        """
        转换为 Anthropic Tool Schema

        将工具定义转换为 Anthropic (Claude) 兼容的格式。
        Anthropic 的格式与 OpenAI 略有不同。

        Anthropic 格式：
        {
            "name": "read_file",
            "description": "读取文件内容",
            "input_schema": {
                "type": "object",
                "properties": {...}
            }
        }

        Returns:
            Dict: 符合 Anthropic 标准的工具 schema
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters
        }

    def __repr__(self) -> str:
        """工具的字符串表示"""
        return f"Tool({self.name})"


class SimpleTool(Tool):
    """
    简单工具基类

    用于快速创建无参数或简单参数的工具。

    使用场景：
    - 工具逻辑简单，不需要单独创建一个类文件
    - 快速原型开发
    - 一次性使用的工具

    示例：
        def hello_world(**kwargs) -> str:
            return "Hello, World!"

        tool = SimpleTool(
            name="hello",
            description="输出 Hello World",
            func=hello_world
        )
    """

    def __init__(self, name: str, description: str, func: callable):
        """
        初始化简单工具

        Args:
            name: 工具名称
            description: 工具描述
            func: 执行函数（接受 **kwargs，返回字符串）
        """
        self._name = name
        self._description = description
        self._func = func

    @property
    def name(self) -> str:
        """返回工具名称"""
        return self._name

    @property
    def description(self) -> str:
        """返回工具描述"""
        return self._description

    def run(self, **kwargs) -> str:
        """
        执行工具

        直接调用传入的函数。

        Args:
            **kwargs: 传递给函数的参数

        Returns:
            str: 函数执行结果
        """
        return self._func(**kwargs)
