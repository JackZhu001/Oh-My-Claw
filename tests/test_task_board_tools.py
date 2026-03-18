import json

from codemate_agent.tools.task.task_board_tools import (
    TaskCleanupTool,
    TaskCreateTool,
    TaskGetTool,
    TaskListTool,
    TaskUpdateTool,
    TeamStatusTool,
)


def test_task_board_tools_create_and_list(tmp_path):
    create_tool = TaskCreateTool(workspace_dir=str(tmp_path))
    list_tool = TaskListTool(workspace_dir=str(tmp_path))

    created = json.loads(create_tool.run(subject="实现登录", description="补充 auth 流程"))
    assert created["id"] == 1
    assert created["status"] == "pending"

    listed = list_tool.run()
    assert "#1" in listed
    assert "实现登录" in listed


def test_task_update_blocks_and_completed_unblocks(tmp_path):
    create_tool = TaskCreateTool(workspace_dir=str(tmp_path))
    get_tool = TaskGetTool(workspace_dir=str(tmp_path))
    update_tool = TaskUpdateTool(workspace_dir=str(tmp_path))

    task1 = json.loads(create_tool.run(subject="重构认证模块"))
    task2 = json.loads(create_tool.run(subject="补充登录页"))
    assert task1["id"] == 1
    assert task2["id"] == 2

    update_tool.run(task_id=1, add_blocks=[2], status="in_progress")
    task2_after_block = json.loads(get_tool.run(task_id=2))
    assert 1 in task2_after_block["blockedBy"]

    update_tool.run(task_id=1, status="completed")
    task1_after_done = json.loads(get_tool.run(task_id=1))
    task2_after_done = json.loads(get_tool.run(task_id=2))

    assert task1_after_done["status"] == "completed"
    assert 1 not in task2_after_done["blockedBy"]


def test_task_namespace_filter_and_cleanup(tmp_path):
    create_tool = TaskCreateTool(workspace_dir=str(tmp_path))
    list_tool = TaskListTool(workspace_dir=str(tmp_path))
    cleanup_tool = TaskCleanupTool(workspace_dir=str(tmp_path))
    get_tool = TaskGetTool(workspace_dir=str(tmp_path))

    task_itest = json.loads(create_tool.run(subject="实现健康检查", namespace="ITEST"))
    task_other = json.loads(create_tool.run(subject="修复登录", namespace="PROD"))

    listed_itest = list_tool.run(namespace="ITEST")
    assert f"#{task_itest['id']}" in listed_itest
    assert f"#{task_other['id']}" not in listed_itest

    cleanup_result = json.loads(cleanup_tool.run(namespace="ITEST"))
    assert cleanup_result["deleted_count"] == 1
    assert task_itest["id"] in cleanup_result["deleted_task_ids"]

    assert list_tool.run(namespace="ITEST") == "No tasks."
    assert json.loads(get_tool.run(task_id=task_other["id"]))["id"] == task_other["id"]


def test_team_status_contains_runtime_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAM_AGENT_ENABLED", "true")
    monkeypatch.setenv("TEAM_NAME", "qa")
    monkeypatch.setenv("TEAM_AGENT_NAME", "lead")
    monkeypatch.setenv("TEAM_AGENT_ROLE", "lead")

    create_tool = TaskCreateTool(workspace_dir=str(tmp_path))
    team_status_tool = TeamStatusTool(workspace_dir=str(tmp_path))

    create_tool.run(subject="ITEST: 实现健康检查")

    inbox_file = tmp_path / ".team" / "inbox" / "lead.jsonl"
    inbox_file.parent.mkdir(parents=True, exist_ok=True)
    inbox_file.write_text('{"type":"message","from":"qa-bot","content":"ping","timestamp":1}\n', encoding="utf-8")

    events_file = tmp_path / ".team" / "events.jsonl"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    events_file.write_text(
        '{"event":"background_results"}\n{"event":"inbox_ingested"}\n',
        encoding="utf-8",
    )

    payload = json.loads(team_status_tool.run(event_limit=1))
    assert payload["enabled"] is True
    assert payload["team_name"] == "qa"
    assert payload["agent_name"] == "lead"
    assert payload["inbox_pending"] == 1
    assert payload["task_stats"]["total"] == 1
    assert payload["events_total"] == 2
    assert payload["recent_events"] == ["inbox_ingested"]
