import threading

from codemate_agent.agent.agent import CodeMateAgent
from codemate_agent.agent.team_runtime import TeamRuntime
from codemate_agent.commands.handler import handle_command
from codemate_agent.schema import LLMResponse
from codemate_agent.schema import Message
from codemate_agent.team.coordinator import TeamCoordinator
from codemate_agent.team import MessageBus, RequestTracker, TaskBoard
from codemate_agent.tools.registry import ToolRegistry


class TeamDummyLLM:
    model = "dummy-model"

    def complete(self, messages, tools=None):
        return LLMResponse(content="done", tool_calls=None, finish_reason="stop", usage=None)


class DelegationDummyLLM:
    model = "delegation-model"

    def complete(self, messages, tools=None):
        return LLMResponse(content="delegated", tool_calls=None, finish_reason="stop", usage=None)


def test_message_bus_read_and_drain(tmp_path):
    bus = MessageBus(tmp_path / "inbox")
    bus.send("lead", "alice", "hello")
    assert bus.inbox_size("alice") == 1

    preview = bus.read_inbox("alice", drain=False)
    assert len(preview) == 1
    assert preview[0]["content"] == "hello"
    assert bus.inbox_size("alice") == 1

    drained = bus.read_inbox("alice", drain=True)
    assert len(drained) == 1
    assert bus.inbox_size("alice") == 0


def test_request_tracker_ingests_shutdown_response():
    tracker = RequestTracker()
    request = tracker.create_request("shutdown", sender="lead", target="alice")
    tracker.ingest_message(
        {
            "type": "shutdown_response",
            "from": "alice",
            "content": "ok",
            "request_id": request.request_id,
            "approve": True,
        }
    )
    snapshot = tracker.snapshot()
    assert snapshot["counts"]["shutdown"]["approved"] == 1
    assert snapshot["counts"]["shutdown"]["pending"] == 0


def test_task_board_claim_is_atomic(tmp_path):
    board = TaskBoard(tmp_path / ".tasks")
    task = board.create_task("Implement feature X")
    winners = []

    def _claim(owner: str):
        claimed = board.claim_task(task["id"], owner)
        if claimed:
            winners.append(owner)

    t1 = threading.Thread(target=_claim, args=("alice",))
    t2 = threading.Thread(target=_claim, args=("bob",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(winners) == 1
    claimed_task = board.get_task(task["id"])
    assert claimed_task is not None
    assert claimed_task["owner"] == winners[0]
    assert claimed_task["status"] == "in_progress"


def test_agent_team_runtime_ingests_inbox_and_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("TEAM_AGENT_ENABLED", "true")
    monkeypatch.setenv("TEAM_AGENT_NAME", "lead")
    monkeypatch.setenv("TEAM_AGENT_ROLE", "lead")
    monkeypatch.setenv("TEAM_NAME", "test-team")

    agent = CodeMateAgent(
        llm_client=TeamDummyLLM(),
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )
    assert agent.message_bus is not None
    agent.message_bus.send("alice", "lead", "please review")

    result = agent.run("hello")
    assert result == "done"
    assert any("<identity>" in (m.content or "") for m in agent.messages if m.role == "system")
    assert any("<team_update>" in (m.content or "") for m in agent.messages if m.role == "system")

    status = agent.get_team_status()
    assert status["enabled"] is True
    assert status["team_name"] == "test-team"

    # 新增可观测命令可执行
    handle_command("/team", agent)
    handle_command("/inbox", agent)
    handle_command("/tasks", agent)


def test_team_runtime_status_includes_dispatch_metadata(tmp_path):
    coordinator = TeamCoordinator(
        workspace_dir=tmp_path,
        main_llm_client=DelegationDummyLLM(),
        light_llm_client=DelegationDummyLLM(),
        tool_registry=ToolRegistry(),
    )
    runtime = TeamRuntime(
        enabled=True,
        workspace_dir=tmp_path,
        team_name="default",
        agent_name="lead",
        agent_role="lead",
        tool_registry=ToolRegistry(),
        messages=[Message(role="system", content="x")],
        session_id_provider=lambda: "sid",
        round_provider=lambda: 1,
        team_coordinator=coordinator,
    )
    status = runtime.get_status()
    assert status["dispatch_enabled"] is True
    assert "builder" in status["members"]
    assert status["queue"]["global_limit"] >= 1


def test_team_runtime_dispatch_task_uses_coordinator(tmp_path):
    coordinator = TeamCoordinator(
        workspace_dir=tmp_path,
        main_llm_client=DelegationDummyLLM(),
        light_llm_client=DelegationDummyLLM(),
        tool_registry=ToolRegistry(),
    )
    runtime = TeamRuntime(
        enabled=True,
        workspace_dir=tmp_path,
        team_name="default",
        agent_name="lead",
        agent_role="lead",
        tool_registry=ToolRegistry(),
        messages=[Message(role="system", content="x")],
        session_id_provider=lambda: "sid",
        round_provider=lambda: 1,
        team_coordinator=coordinator,
    )

    result = runtime.dispatch_task(
        agent_id="researcher",
        title="Inspect docs",
        instructions="Read docs and summarize",
        context_summary="project context",
    )
    assert result.success is True
    assert result.agent_id == "researcher"
    task = coordinator.task_board.get_task(result.task_id)
    assert task is not None
    assert task["delegated_by"] == "lead"
