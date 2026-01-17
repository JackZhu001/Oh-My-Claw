"""
数据模型定义

整个 Agent 系统的数据结构说明书。

使用 Pydantic 进行数据验证和序列化。
这是整个项目的数据结构基础，定义了 Agent 运行过程中的所有数据格式。

核心概念：
1. Message: 聊天消息，用于与 LLM 交互
2. ToolCall: 工具调用，LLM 决定调用哪个工具及参数
3. LLMResponse: LLM 的响应，包含内容和可能的工具调用
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class LLMProvider(str, Enum):
    """
    LLM 提供商类型

    定义支持的 LLM 提供商，便于扩展支持多种模型。
    """
    ANTHROPIC = "anthropic"  # Claude 系列
    OPENAI = "openai"        # GPT 系列
    ZHIPU = "zhipu"          # 智谱 GLM 系列


class TokenUsage(BaseModel):
    """
    Token 使用统计

    用于跟踪 API 调用的成本，帮助控制使用量。
    """
    prompt_tokens: int = 0        # 输入 token 数（提示词 + 消息历史）
    completion_tokens: int = 0    # 输出 token 数（LLM 生成的内容）
    total_tokens: int = 0         # 总 token 数


class FunctionCall(BaseModel):
    """
    函数调用详情

    当 LLM 决定调用工具时，会返回函数名和参数。
    这是 Function Calling 的核心数据结构。

    例如：
        name = "read_file"
        arguments = {"file_path": "/path/to/file.py"}
    """
    name: str                           # 要调用的函数/工具名称
    arguments: dict[str, Any] = Field(default_factory=dict)  # 函数参数（JSON 对象）


class ToolCall(BaseModel):
    """
    工具调用结构

    OpenAI Function Calling API 返回的完整工具调用格式。
    包含唯一 ID、类型和具体的函数调用信息。

    例如：
        id = "call_abc123"
        type = "function"
        function = {"name": "read_file", "arguments": {...}}
    """
    id: str = ""                    # 工具调用的唯一标识符，用于关联请求和响应
    type: str = "function"          # 调用类型，目前固定为 "function"
    function: FunctionCall          # 具体的函数调用信息


class Message(BaseModel):
    """
    聊天消息

    表示对话中的一条消息，可以是多种角色：
    - system: 系统提示词，设定 Agent 的行为
    - user: 用户输入
    - assistant: LLM 的回复（可能包含 tool_calls）
    - tool: 工具执行的结果

    消息流示例：
        user: "分析这个项目"
        assistant: [tool_calls: list_dir]
        tool: [目录列表]
        assistant: "这个项目包含..."
    """
    role: str = Field(..., description="消息角色: system, user, assistant, tool")
    content: str = ""                                    # 消息文本内容
    tool_calls: Optional[list[ToolCall]] = None          # assistant 消息可能包含工具调用
    tool_call_id: Optional[str] = None                   # tool 消息需要关联到对应的 tool_call
    name: Optional[str] = None                           # tool 消息的工具名称


class LLMResponse(BaseModel):
    """
    LLM 响应

    LLM API 返回的完整响应结构。
    LLM 可以选择：
    1. 直接返回文本答案（finish_reason = "stop"）
    2. 请求调用工具（finish_reason = "tool_calls"）

    这决定了 Agent 是继续执行工具还是返回结果给用户。
    """
    content: str = ""                            # LLM 生成的文本内容
    tool_calls: Optional[list[ToolCall]] = None  # 如果 LLM 请求调用工具
    finish_reason: str = ""                      # 结束原因: stop, tool_calls, length, error
    usage: Optional[TokenUsage] = None           # 本次请求的 token 使用统计


class ToolResult(BaseModel):
    """
    工具执行结果

    工具执行后的返回结果，包含成功/失败状态和详细信息。
    """
    success: bool                # 执行是否成功
    content: str = ""            # 执行结果内容
    error: Optional[str] = None  # 错误信息（如果失败）


class AgentState(BaseModel):
    """
    Agent 状态

    记录 Agent 运行过程中的完整状态，可用于：
    - 持久化保存对话历史
    - 断点恢复
    - 调试和监控

    例如保存到文件后，下次启动可以恢复之前的对话。
    """
    messages: list[Message] = Field(default_factory=list)  # 完整的消息历史
    round_count: int = 0                                    # 当前轮数
    max_rounds: int = 50                                    # 最大轮数限制
    finished: bool = False                                  # 是否已完成
    total_tokens: int = 0                                   # 累计 token 消耗


class Parameter(BaseModel):
    """
    工具参数定义

    用于描述工具的输入参数，采用 JSON Schema 格式。
    LLM 根据此定义知道如何正确调用工具。

    例如 read_file 工具的参数：
        type = "object"
        properties = {
            "file_path": {
                "type": "string",
                "description": "要读取的文件路径"
            }
        }
        required = ["file_path"]
    """
    type: str = "string"                      # 参数类型: string, number, boolean, array, object
    description: str = ""                     # 参数描述，告诉 LLM 这个参数的作用
    enum: Optional[list[Any]] = None          # 可选值枚举（如果有固定选项）
    properties: Optional[dict[str, Any]] = None  # 嵌套属性（当 type 为 object 时）
    required: list[str] = Field(default_factory=list)  # 必填参数列表


class ToolSchema(BaseModel):
    """
    工具 Schema

    完整的工具定义，用于发送给 LLM。
    LLM 根据这些信息决定何时调用哪个工具。

    OpenAI 格式：
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取文件内容",
                "parameters": {...}
            }
        }
    """
    type: str = "function"                    # 固定为 "function"
    function: dict[str, Any] = Field(default_factory=dict)  # 函数定义（name, description, parameters）
