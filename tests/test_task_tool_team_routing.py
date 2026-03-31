import time
import pytest

from codemate_agent.schema import LLMResponse
from codemate_agent.team.coordinator import StrictWorkflowError
from codemate_agent.team.definitions import ExecutionResult
from codemate_agent.tools.registry import ToolRegistry
from codemate_agent.tools.task.task_tool import TaskTool


class DummyLLM:
    model = "dummy"

    def complete(self, messages, tools=None):
        return LLMResponse(content="local fallback", tool_calls=None, finish_reason="stop")


class DummyCoordinator:
    def __init__(self):
        self.calls = []

    def dispatch_to(self, **kwargs):
        self.calls.append(kwargs)
        now = time.time()
        return ExecutionResult(
            request_id="req-1",
            task_id=7,
            agent_id=kwargs["agent_id"],
            status="completed",
            summary="Delegated execution finished.",
            artifact_paths=[],
            session_id=f"{kwargs['agent_id']}-sess",
            error="",
            tool_usage={"read_file": 1},
            started_at=now,
            finished_at=now,
        )


class DummyDelegateHandler:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        now = time.time()
        return ExecutionResult(
            request_id="req-h",
            task_id=8,
            agent_id=kwargs["agent_id"],
            status="completed",
            summary="Runtime delegated.",
            artifact_paths=[],
            session_id=f"{kwargs['agent_id']}-handler",
            error="",
            tool_usage={},
            started_at=now,
            finished_at=now,
        )


class StrictViolationCoordinator:
    def dispatch_to(self, **kwargs):
        raise StrictWorkflowError("TEAM_STRICT_MODE 约束：builder 阶段前必须先完成 researcher 阶段。")


class GenericFailureCoordinator:
    def dispatch_to(self, **kwargs):
        raise RuntimeError("dispatch lane unavailable")


def test_task_tool_prefers_team_coordinator_route(tmp_path):
    coordinator = DummyCoordinator()
    tool = TaskTool(working_dir=str(tmp_path))
    tool.set_dependencies(
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
        team_coordinator=coordinator,
    )

    output = tool.run(
        description="Explore architecture",
        prompt="Inspect README and summarize.",
        subagent_type="explore",
    )

    assert coordinator.calls
    assert coordinator.calls[0]["agent_id"] == "researcher"
    assert "target_agent: researcher" in coordinator.calls[0]["context_summary"]
    assert "子代理类型: team:researcher" in output
    assert "Delegated execution finished." in output


def test_task_tool_prefers_delegate_handler_over_coordinator(tmp_path):
    coordinator = DummyCoordinator()
    handler = DummyDelegateHandler()
    tool = TaskTool(working_dir=str(tmp_path))
    tool.set_dependencies(
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
        team_coordinator=coordinator,
        delegate_handler=handler,
    )

    output = tool.run(
        description="Review changes",
        prompt="Check the latest patch",
        subagent_type="summary",
    )

    assert handler.calls
    assert not coordinator.calls
    assert handler.calls[0]["agent_id"] == "reviewer"
    assert "target_agent: reviewer" in handler.calls[0]["context_summary"]
    assert "Runtime delegated." in output


def test_task_tool_returns_strict_violation_without_local_fallback(tmp_path):
    tool = TaskTool(working_dir=str(tmp_path))
    tool.set_dependencies(
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
        team_coordinator=StrictViolationCoordinator(),
    )

    output = tool.run(
        description="Build page",
        prompt="Write docs/welcome.html",
        subagent_type="general",
    )
    assert "TEAM_STRICT_VIOLATION" in output
    assert "local fallback" not in output


def test_task_tool_accepts_team_role_alias_for_subagent_type(tmp_path):
    coordinator = DummyCoordinator()
    tool = TaskTool(working_dir=str(tmp_path))
    tool.set_dependencies(
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
        team_coordinator=coordinator,
    )

    output = tool.run(
        description="Collect facts",
        prompt="Read project docs",
        subagent_type="researcher",
    )

    assert coordinator.calls
    assert coordinator.calls[0]["agent_id"] == "researcher"
    assert "子代理类型: team:researcher" in output


def test_task_tool_dispatch_failure_does_not_fallback_to_local_subagent(tmp_path):
    tool = TaskTool(working_dir=str(tmp_path))
    tool.set_dependencies(
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
        team_coordinator=GenericFailureCoordinator(),
    )

    output = tool.run(
        description="Collect facts",
        prompt="Read project docs",
        subagent_type="researcher",
    )
    assert "TEAM_DISPATCH_ERROR" in output
    assert "local fallback" not in output


def test_task_tool_strict_mode_requires_explicit_agent_id(monkeypatch, tmp_path):
    monkeypatch.setenv("TEAM_STRICT_MODE", "true")
    coordinator = DummyCoordinator()
    tool = TaskTool(working_dir=str(tmp_path))
    tool.set_dependencies(
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
        team_coordinator=coordinator,
    )
    output = tool.run(
        description="Build page",
        prompt="Create docs page",
        subagent_type="general",
    )
    assert "TEAM_STRICT_VIOLATION" in output
    assert "必须显式传入 agent_id" in output
    assert not coordinator.calls


def test_task_tool_strict_mode_accepts_explicit_agent_id(monkeypatch, tmp_path):
    monkeypatch.setenv("TEAM_STRICT_MODE", "true")
    coordinator = DummyCoordinator()
    tool = TaskTool(working_dir=str(tmp_path))
    tool.set_dependencies(
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
        team_coordinator=coordinator,
    )
    output = tool.run(
        description="Build page",
        prompt="Create docs page",
        subagent_type="general",
        agent_id="builder",
    )
    assert coordinator.calls
    assert coordinator.calls[0]["agent_id"] == "builder"
    assert "子代理类型: team:builder" in output
