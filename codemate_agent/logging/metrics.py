"""
Metrics 统计 - Token 使用、成本估算、性能指标

提供轻量级的会话指标统计功能。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# GLM-4 价格（仅供参考，实际价格可能变动）
# https://open.bigmodel.cn/pricing
GLM_PRICING = {
    "glm-4": {"input": 0.0001, "output": 0.0005},  # 每 1K tokens
    "glm-4-flash": {"input": 0.0001, "output": 0.0001},
    "glm-4-plus": {"input": 0.0005, "output": 0.001},
}


@dataclass
class TokenUsage:
    """单次 LLM 调用的 Token 使用情况"""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """合并两次使用情况"""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "TokenUsage":
        """从字典创建"""
        input_tokens = data.get("input_tokens", data.get("prompt_tokens", 0))
        output_tokens = data.get("output_tokens", data.get("completion_tokens", 0))
        total_tokens = data.get("total_tokens", input_tokens + output_tokens)
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


@dataclass
class ToolCallStats:
    """工具调用统计"""

    calls: dict[str, int] = field(default_factory=dict)
    errors: dict[str, int] = field(default_factory=dict)
    total_calls: int = 0
    total_errors: int = 0

    def record_call(self, tool_name: str, success: bool = True) -> None:
        """记录一次工具调用"""
        self.total_calls += 1
        self.calls[tool_name] = self.calls.get(tool_name, 0) + 1

        if not success:
            self.total_errors += 1
            self.errors[tool_name] = self.errors.get(tool_name, 0) + 1


@dataclass
class SessionMetrics:
    """
    会话指标统计

    跟踪整个会话期间的：
    - Token 使用量
    - 预估成本
    - 工具调用统计
    - 执行时间
    """

    session_id: str
    model: str = "glm-4"
    start_time: datetime = field(default_factory=lambda: datetime.now())
    end_time: Optional[datetime] = None

    # Token 统计
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # 成本统计（单位：元）
    estimated_cost: float = 0.0

    # 执行统计
    total_rounds: int = 0
    tool_calls: ToolCallStats = field(default_factory=ToolCallStats)
    errors: int = 0

    # 性能统计
    llm_calls: int = 0
    llm_total_duration_ms: float = 0.0

    @property
    def duration_seconds(self) -> float:
        """获取会话持续时间（秒）"""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def avg_llm_duration_ms(self) -> float:
        """平均 LLM 调用耗时（毫秒）"""
        if self.llm_calls == 0:
            return 0.0
        return self.llm_total_duration_ms / self.llm_calls

    def record_llm_call(
        self,
        usage: TokenUsage | dict,
        duration_ms: float = 0.0,
    ) -> None:
        """
        记录一次 LLM 调用

        Args:
            usage: Token 使用情况 (TokenUsage 对象或字典)
            duration_ms: 调用耗时（毫秒）

        注意: 支持多种 Token 格式以兼容不同的 LLM API
        - prompt_tokens / completion_tokens (OpenAI/GLM 格式)
        - input_tokens / output_tokens (通用格式)
        """
        # 将 usage 转换为字典以处理不同格式
        if isinstance(usage, dict):
            usage_dict = usage
        else:
            usage_dict = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }

        # 提取 token 数（支持多种命名）
        input_tokens = (
            usage_dict.get("input_tokens") or
            usage_dict.get("prompt_tokens", 0)
        )
        output_tokens = (
            usage_dict.get("output_tokens") or
            usage_dict.get("completion_tokens", 0)
        )
        total_tokens = usage_dict.get("total_tokens", input_tokens + output_tokens)

        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += total_tokens

        # 计算 cost
        pricing = GLM_PRICING.get(self.model, GLM_PRICING["glm-4"])
        cost = (
            input_tokens / 1000 * pricing["input"]
            + output_tokens / 1000 * pricing["output"]
        )
        self.estimated_cost += cost

        self.llm_calls += 1
        self.llm_total_duration_ms += duration_ms

    def record_tool_call(self, tool_name: str, success: bool = True) -> None:
        """记录一次工具调用"""
        self.tool_calls.record_call(tool_name, success)

    def record_round(self) -> None:
        """记录一个执行回合"""
        self.total_rounds += 1

    def record_error(self) -> None:
        """记录一次错误"""
        self.errors += 1

    def finalize(self) -> dict:
        """
        结束会话并返回统计摘要

        Returns:
            统计信息字典
        """
        self.end_time = datetime.now()

        return {
            "session_id": self.session_id,
            "model": self.model,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": round(self.duration_seconds, 2),
            "tokens": {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "total": self.total_tokens,
            },
            "estimated_cost": round(self.estimated_cost, 4),
            "execution": {
                "total_rounds": self.total_rounds,
                "llm_calls": self.llm_calls,
                "tool_calls": self.tool_calls.calls,
                "errors": self.errors,
            },
            "performance": {
                "avg_llm_duration_ms": round(self.avg_llm_duration_ms, 2),
            },
        }

    def print_summary(self) -> None:
        """打印格式化的统计摘要到终端"""
        print()
        print("📊 ──────────────────────────────────────────")
        print(f"   CodeMate Agent 会话统计")
        print("──────────────────────────────────────────")
        print(f"  会话 ID     : {self.session_id}")
        print(f"  模型        : {self.model}")
        print(f"  持续时间    : {self.duration_seconds:.1f} 秒")
        print()
        print(f"  🪙 Token 使用")
        print(f"     Input   : {self.input_tokens:,}")
        print(f"     Output  : {self.output_tokens:,}")
        print(f"     Total   : {self.total_tokens:,}")
        print()
        print(f"  💰 预估成本 : ¥{self.estimated_cost:.4f}")
        print()
        print(f"  🔄 执行统计")
        print(f"     总轮数     : {self.total_rounds}")
        print(f"     LLM 调用   : {self.llm_calls}")
        print(f"     工具调用   : {self.tool_calls.total_calls}")
        if self.tool_calls.calls:
            print(f"       调用详情 :")
            for tool, count in sorted(self.tool_calls.calls.items()):
                print(f"         - {tool}: {count}")
        print(f"     错误次数   : {self.errors}")
        print("──────────────────────────────────────────")

    def save(self, output_dir: Path) -> Path:
        """
        保存统计信息到 JSON 文件

        Args:
            output_dir: 输出目录

        Returns:
            保存的文件路径
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        file_path = output_dir / f"metrics-{self.session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.finalize(), f, ensure_ascii=False, indent=2)

        return file_path
