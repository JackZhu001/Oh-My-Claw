#!/usr/bin/env python3
"""
测试 Subagent 功能

验证：
1. TaskTool 工具创建和依赖注入
2. 子代理能正确执行只读任务
3. 不同类型的子代理（general/explore/plan）
4. 工具访问限制（不能 write_file, run_shell）
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from codemate_agent.llm.client import GLMClient
from codemate_agent.tools import get_all_tools, get_tool_registry
from codemate_agent.subagent.subagent import TaskTool, SubagentRunner, SUBAGENT_TYPES, ALLOWED_TOOLS, DENIED_TOOLS


def test_task_tool_creation():
    """测试 TaskTool 创建和依赖注入"""
    print("=" * 60)
    print("测试 1: TaskTool 创建")
    print("=" * 60)

    # 获取基础工具注册器（模拟 Agent 的行为）
    registry = get_tool_registry()

    # 创建并注册 TaskTool（模拟 Agent 的行为）
    task_tool = TaskTool(working_dir=str(Path(__file__).parent))
    print(f"✓ TaskTool 创建成功")
    print(f"  - 工具名: {task_tool.name}")
    print(f"  - 描述: {task_tool.description[:100]}...")

    # 测试依赖注入
    try:
        api_key = os.getenv("GLM_API_KEY")
        if not api_key:
            print("  ! GLM_API_KEY 未设置，跳过依赖注入测试")
            return True

        llm = GLMClient(api_key=api_key)
        task_tool.set_dependencies(llm, registry)
        print("✓ TaskTool 依赖注入成功")
        return True
    except Exception as e:
        print(f"✗ TaskTool 依赖注入失败: {e}")
        return False


def test_subagent_tool_restrictions():
    """测试子代理工具限制"""
    print("\n" + "=" * 60)
    print("测试 2: 子代理工具限制")
    print("=" * 60)

    print(f"允许的工具: {ALLOWED_TOOLS}")
    print(f"禁止的工具: {DENIED_TOOLS}")

    # 检查危险工具不在允许列表中
    dangerous = {"write_file", "edit_file", "delete_file", "append_file", "run_shell", "task"}
    if dangerous.isdisjoint(ALLOWED_TOOLS):
        print("✓ 危险工具已正确排除")
    else:
        print("✗ 危险工具未正确排除")
        return False

    # 检查只读工具在允许列表中（使用正确的工具名称）
    readonly = {"list_dir", "search_files", "search_code", "read_file", "todo_write"}
    if readonly.issubset(ALLOWED_TOOLS):
        print("✓ 只读工具已正确包含")
    else:
        print("✗ 只读工具未正确包含")
        missing = readonly - ALLOWED_TOOLS
        print(f"  缺失工具: {missing}")
        return False

    return True


def test_subagent_runner():
    """测试子代理运行器"""
    print("\n" + "=" * 60)
    print("测试 3: 子代理运行器")
    print("=" * 60)

    # 初始化 LLM 客户端
    try:
        api_key = os.getenv("GLM_API_KEY")
        if not api_key:
            print("✗ GLM_API_KEY 未设置")
            return False

        llm = GLMClient(api_key=api_key)
        print("✓ LLM 客户端初始化成功")
    except Exception as e:
        print(f"✗ LLM 客户端初始化失败: {e}")
        return False

    # 获取工具注册器
    tools = get_all_tools()
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)

    # 测试 explore 子代理
    print("\n测试 explore 子代理...")
    runner = SubagentRunner(
        llm_client=llm,
        tool_registry=registry,
        subagent_type="explore",
        max_steps=10,
        workspace_dir=Path(__file__).parent,
    )

    print(f"✓ SubagentRunner 创建成功")
    print(f"  - 子代理类型: explore")
    print(f"  - 最大步数: 10")
    print(f"  - 可用工具: {list(runner.tool_registry.get_all().keys())}")

    # 验证工具限制
    available_tools = set(runner.tool_registry.get_all().keys())
    if available_tools.issubset(ALLOWED_TOOLS):
        print(f"✓ 子代理工具限制正确")
    else:
        print(f"✗ 子代理工具限制错误: {available_tools - ALLOWED_TOOLS}")
        return False

    return True, llm, registry


def test_explore_subagent_execution(llm, registry):
    """测试 explore 子代理实际执行"""
    print("\n" + "=" * 60)
    print("测试 4: Explore 子代理实际执行")
    print("=" * 60)

    runner = SubagentRunner(
        llm_client=llm,
        tool_registry=registry,
        subagent_type="explore",
        max_steps=15,
        workspace_dir=Path(__file__).parent,
    )

    # 执行一个简单的探索任务
    task_desc = "探索项目结构"
    task_prompt = """
    请探索当前项目的结构，重点关注：
    1. 主要的目录和文件
    2. codemate_agent 目录下的模块
    3. 总结项目的主要组件

    使用 list_files 和 read_file 工具完成探索。
    """

    print(f"任务描述: {task_desc}")
    print(f"执行中...")

    try:
        result = runner.run(task_desc, task_prompt)

        print(f"\n✓ 子代理执行完成")
        print(f"  - 状态: {'成功' if result.success else '失败'}")
        print(f"  - 步数: {result.steps_taken}")
        print(f"  - 工具使用: {result.tool_usage}")

        if result.error:
            print(f"  - 错误: {result.error}")

        print(f"\n--- 子代理返回结果 ---")
        print(result.content[:500] + "..." if len(result.content) > 500 else result.content)

        return result.success

    except Exception as e:
        print(f"✗ 子代理执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_task_tool_direct(llm, registry):
    """测试 TaskTool 直接调用"""
    print("\n" + "=" * 60)
    print("测试 5: TaskTool 直接调用")
    print("=" * 60)

    task_tool = TaskTool(working_dir=str(Path(__file__).parent))
    task_tool.set_dependencies(llm, registry)

    result = task_tool.run(
        description="列出项目文件",
        prompt="请使用 list_files 工具列出当前目录的文件和文件夹",
        subagent_type="general"
    )

    print(result[:500] + "..." if len(result) > 500 else result)

    if "--- TASK RESULT ---" in result and "执行状态: 成功" in result:
        print("\n✓ TaskTool 调用成功")
        return True
    else:
        print("\n✗ TaskTool 调用失败")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Subagent 功能测试")
    print("=" * 60)

    results = []

    # 测试 1: TaskTool 创建
    results.append(("TaskTool 创建", test_task_tool_creation()))

    # 测试 2: 工具限制
    results.append(("工具限制", test_subagent_tool_restrictions()))

    # 测试 3: 运行器初始化
    test3_result = test_subagent_runner()
    if test3_result is True:
        results.append(("运行器初始化", True))
    elif isinstance(test3_result, tuple):
        results.append(("运行器初始化", test3_result[0]))
        llm, registry = test3_result[1], test3_result[2]

        # 测试 4: 实际执行
        if os.getenv("GLM_API_KEY"):
            results.append(("Explore 执行", test_explore_subagent_execution(llm, registry)))
            results.append(("TaskTool 调用", test_task_tool_direct(llm, registry)))
        else:
            print("\n跳过执行测试（未设置 GLM_API_KEY）")

    # 总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)

    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status} - {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n总计: {passed}/{total} 测试通过")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
