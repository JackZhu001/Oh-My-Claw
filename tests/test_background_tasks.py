import re
import time

from codemate_agent.agent.agent import CodeMateAgent
from codemate_agent.schema import LLMResponse
from codemate_agent.tools.shell.background_tasks import (
    BackgroundRunTool,
    CheckBackgroundTool,
    _BackgroundTaskManager,
    drain_background_notifications,
)


class BackgroundDummyLLM:
    model = "dummy-model"

    def complete(self, messages, tools=None):
        return LLMResponse(content="done", tool_calls=None, finish_reason="stop", usage=None)


def _wait_task_finished(check_tool: CheckBackgroundTool, task_id: str) -> str:
    result = ""
    for _ in range(50):
        result = check_tool.run(task_id=task_id)
        if "[running]" not in result:
            return result
        time.sleep(0.1)
    return result


def test_background_tools_run_check_and_drain(tmp_path):
    run_tool = BackgroundRunTool(workspace_dir=str(tmp_path))
    check_tool = CheckBackgroundTool(workspace_dir=str(tmp_path))

    started = run_tool.run(command="echo background-ok")
    match = re.search(r"Background task ([0-9a-f]{8}) started", started)
    assert match is not None
    task_id = match.group(1)

    status = _wait_task_finished(check_tool, task_id)
    assert "[completed]" in status
    assert "background-ok" in status

    notifications = drain_background_notifications(tmp_path, limit=20)
    assert any(item["task_id"] == task_id for item in notifications)
    assert drain_background_notifications(tmp_path, limit=20) == []


def test_background_run_supports_bash_lc_with_quoted_chain(tmp_path):
    run_tool = BackgroundRunTool(workspace_dir=str(tmp_path))
    check_tool = CheckBackgroundTool(workspace_dir=str(tmp_path))

    started = run_tool.run(command='bash -lc "echo one && echo two"', timeout=30)
    match = re.search(r"Background task ([0-9a-f]{8}) started", started)
    assert match is not None
    task_id = match.group(1)

    status = _wait_task_finished(check_tool, task_id)
    assert "[completed]" in status
    assert "one" in status
    assert "two" in status


def test_background_run_deduplicates_same_running_command(tmp_path):
    run_tool = BackgroundRunTool(workspace_dir=str(tmp_path))
    check_tool = CheckBackgroundTool(workspace_dir=str(tmp_path))
    cmd = "bash -lc \"sleep 1\""

    first = run_tool.run(command=cmd, timeout=30)
    first_id = re.search(r"Background task ([0-9a-f]{8}) started", first).group(1)

    blocked = run_tool.run(command=cmd, timeout=30)
    assert f"请先检查上一个后台任务状态: {first_id}" in blocked

    _ = check_tool.run(task_id=first_id)
    duplicate = run_tool.run(command=cmd, timeout=30)
    assert f"Background task {first_id} already running" in duplicate


def test_background_command_normalization_handles_wrapper_and_quotes(tmp_path):
    manager = _BackgroundTaskManager(tmp_path)
    wrapped = 'bash -lc "sleep 2 && echo health api done"'
    plain = 'sleep 2 && echo "health api done"'
    assert manager._normalize_command(wrapped) == manager._normalize_command(plain)


def test_background_run_blocks_new_task_until_polled_or_parallel(tmp_path):
    run_tool = BackgroundRunTool(workspace_dir=str(tmp_path))
    check_tool = CheckBackgroundTool(workspace_dir=str(tmp_path))

    first = run_tool.run(command="bash -lc \"sleep 1\"", timeout=30)
    first_id = re.search(r"Background task ([0-9a-f]{8}) started", first).group(1)

    blocked = run_tool.run(command="echo second", timeout=30)
    assert f"请先检查上一个后台任务状态: {first_id}" in blocked

    _ = check_tool.run(task_id=first_id)
    parallel = run_tool.run(command="echo second", timeout=30, allow_parallel=True)
    assert re.search(r"Background task ([0-9a-f]{8}) started", parallel)


def test_background_run_requires_check_before_next_task_even_if_done(tmp_path):
    run_tool = BackgroundRunTool(workspace_dir=str(tmp_path))
    check_tool = CheckBackgroundTool(workspace_dir=str(tmp_path))

    first = run_tool.run(command="echo first", timeout=30)
    first_id = re.search(r"Background task ([0-9a-f]{8}) started", first).group(1)
    time.sleep(0.1)

    blocked = run_tool.run(command="echo second", timeout=30)
    assert f"请先检查上一个后台任务状态: {first_id}" in blocked

    _ = check_tool.run(task_id=first_id)
    second = run_tool.run(command="echo second", timeout=30)
    assert re.search(r"Background task ([0-9a-f]{8}) started", second)


def test_agent_ingests_background_notifications(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("BACKGROUND_TASKS_ENABLED", "true")

    run_tool = BackgroundRunTool(workspace_dir=str(tmp_path))
    check_tool = CheckBackgroundTool(workspace_dir=str(tmp_path))
    started = run_tool.run(command="echo notify-me")
    task_id = re.search(r"Background task ([0-9a-f]{8}) started", started).group(1)
    _wait_task_finished(check_tool, task_id)

    agent = CodeMateAgent(
        llm_client=BackgroundDummyLLM(),
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )
    result = agent.run("hello")
    assert result == "done"
    assert any(
        msg.role == "system" and "<background_results>" in (msg.content or "")
        for msg in agent.messages
    )
