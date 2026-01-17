"""测试进度显示功能"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from codemate_agent.cli import ProgressDisplay


def test_progress_display():
    """测试进度显示组件"""
    console = Console()
    pd = ProgressDisplay(console)

    print("=== 测试进度显示 ===\n")

    # 模拟轮次开始
    pd.on_event("round_start", {"round": 1, "max_rounds": 10})

    # 模拟工具调用
    pd.on_event("tool_call_start", {
        "tool": "write_file",
        "args": "file=test.py"
    })
    pd.on_event("tool_call_end", {"tool": "write_file", "success": True})

    # 模拟第二轮
    pd.on_event("round_start", {"round": 2, "max_rounds": 10})

    pd.on_event("tool_call_start", {
        "tool": "read_file",
        "args": "file=test.py"
    })

    print("\n=== 测试完成 ===")
    print("✓ 进度显示功能正常")


if __name__ == "__main__":
    test_progress_display()
