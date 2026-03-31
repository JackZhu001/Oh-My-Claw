import pytest

from codemate_agent.schema import LLMResponse
from codemate_agent.team.coordinator import StrictWorkflowError, TeamCoordinator
from codemate_agent.team.protocols import RequestTracker
from codemate_agent.tools.registry import ToolRegistry


class DummyLLM:
    model = "dummy"

    def complete(self, messages, tools=None):
        return LLMResponse(content="delegated result", tool_calls=None, finish_reason="stop")


def test_team_coordinator_dispatches_to_member(tmp_path):
    coordinator = TeamCoordinator(
        workspace_dir=tmp_path,
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
    )

    result = coordinator.dispatch_to(
        agent_id="researcher",
        title="Inspect docs",
        instructions="Read key docs and summarize.",
        delegated_by="lead",
    )

    assert result.success is True
    assert result.agent_id == "researcher"
    assert result.task_id is not None
    assert result.session_id.startswith("researcher-")

    task = coordinator.task_board.get_task(result.task_id)
    assert task is not None
    assert task["assignee"] == "researcher"
    assert task["delegated_by"] == "lead"
    assert task["status"] == "completed"
    assert task["artifact_dir"]
    assert task["artifact_manifest"]
    assert result.artifact_manifest_path
    assert coordinator.get_queue_stats()["global_limit"] >= 1


def test_team_coordinator_rejects_unknown_member(tmp_path):
    coordinator = TeamCoordinator(
        workspace_dir=tmp_path,
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
    )
    try:
        coordinator.dispatch_to(
            agent_id="ghost",
            title="No-op",
            instructions="Should fail",
        )
    except ValueError as exc:
        assert "unknown team member" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_team_coordinator_strict_mode_enforces_stage_order(monkeypatch, tmp_path):
    monkeypatch.setenv("TEAM_STRICT_MODE", "true")
    tracker = RequestTracker()
    coordinator = TeamCoordinator(
        workspace_dir=tmp_path,
        main_llm_client=DummyLLM(),
        light_llm_client=DummyLLM(),
        tool_registry=ToolRegistry(),
        request_tracker=tracker,
    )

    session_id = "strict-sid"
    with pytest.raises(StrictWorkflowError):
        coordinator.dispatch_to(
            agent_id="builder",
            title="Build page",
            instructions="Write docs page",
            delegated_by="lead",
            parent_session_id=session_id,
        )

    research = coordinator.dispatch_to(
        agent_id="researcher",
        title="Collect facts",
        instructions="Read docs and summarize",
        delegated_by="lead",
        parent_session_id=session_id,
    )
    build = coordinator.dispatch_to(
        agent_id="builder",
        title="Build page",
        instructions="Write docs page",
        delegated_by="lead",
        parent_session_id=session_id,
    )
    review = coordinator.dispatch_to(
        agent_id="reviewer",
        title="Review page",
        instructions="Check consistency",
        delegated_by="lead",
        parent_session_id=session_id,
    )

    assert research.success is True
    assert build.success is True
    assert review.success is True
    snapshot = tracker.snapshot()
    assert snapshot["counts"]["review"]["approved"] == 1
    strict_progress = coordinator.get_strict_progress(session_id)
    assert strict_progress["researcher_done"] is True
    assert strict_progress["builder_done"] is True
    assert strict_progress["reviewer_done"] is True
