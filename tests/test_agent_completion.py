from codemate_agent.agent.agent import CodeMateAgent
from codemate_agent.schema import LLMResponse, ToolCall, FunctionCall
from codemate_agent.tools.todo.todo_write import TodoWriteTool


class DummyLLM:
    model = "dummy-model"

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="<think>继续思考中</think>",
                tool_calls=None,
                finish_reason="stop",
                usage=None,
            )
        return LLMResponse(
            content="已生成文件：docs/index.html",
            tool_calls=None,
            finish_reason="stop",
            usage=None,
        )


class NagTriggerLLM:
    model = "dummy-model"

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        function=FunctionCall(name="missing_tool", arguments={}),
                    )
                ],
                finish_reason="tool_calls",
                usage=None,
            )
        return LLMResponse(content="done", tool_calls=None, finish_reason="stop", usage=None)


class PendingTodoLLM:
    model = "dummy-model"

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="现在进行最终一致性检查",
                tool_calls=None,
                finish_reason="stop",
                usage=None,
            )
        return LLMResponse(
            content="已生成文件：docs/review.md",
            tool_calls=None,
            finish_reason="stop",
            usage=None,
        )


class BackgroundProgressLLM:
    model = "dummy-model"

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content=(
                    "<think>成功启动了后台任务，bg_task_id=06a195a3。"
                    "现在立即再次执行相同的命令，验证去重机制。</think>\n\n"
                    "后台任务启动成功，`bg_task_id=06a195a3`。立即再次执行相同命令验证去重："
                ),
                tool_calls=None,
                finish_reason="stop",
                usage=None,
            )
        return LLMResponse(
            content="已完成并输出最终报告。",
            tool_calls=None,
            finish_reason="stop",
            usage=None,
        )


class DecisionSummaryLLM:
    model = "dummy-model"

    def complete(self, messages, tools=None):
        return LLMResponse(
            content="<think>正在判断下一步</think>\n准备调用 task 子代理分析项目",
            tool_calls=None,
            finish_reason="stop",
            usage=None,
        )


class InspectQueryLLM:
    model = "dummy-model"

    def __init__(self):
        self.last_user_message = ""
        self.last_tool_messages: list[str] = []

    def complete(self, messages, tools=None):
        for msg in reversed(messages):
            if msg.role == "user":
                self.last_user_message = msg.content or ""
                break
        self.last_tool_messages = [msg.content or "" for msg in messages if msg.role == "tool"]
        return LLMResponse(content="ok", tool_calls=None, finish_reason="stop", usage=None)


def _has_todo_nag(messages) -> bool:
    return any(
        msg.role == "system" and "请更新你的任务进度" in (msg.content or "")
        for msg in messages
    )


def test_prevent_premature_finish_when_plan_not_done(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    llm = DummyLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=True,
    )
    # 模拟已有计划但未完成
    agent.planner.current_plan = object()
    agent._todo_all_completed = False

    result = agent.run("生成网页")
    assert "已生成文件" in result
    assert llm.calls == 2


def test_todo_nag_triggers_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("TODO_NAG_INTERVAL", "1")
    monkeypatch.setenv("TODO_NAG_ENABLED", "true")

    agent = CodeMateAgent(
        llm_client=NagTriggerLLM(),
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )
    result = agent.run("run")
    assert result == "done"
    assert _has_todo_nag(agent.messages)


def test_todo_nag_can_be_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("TODO_NAG_INTERVAL", "1")
    monkeypatch.setenv("TODO_NAG_ENABLED", "false")

    agent = CodeMateAgent(
        llm_client=NagTriggerLLM(),
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )
    result = agent.run("run")
    assert result == "done"
    assert not _has_todo_nag(agent.messages)


def test_prevent_finish_when_todo_still_pending(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    TodoWriteTool.clear()
    TodoWriteTool._current_summary = "review"
    TodoWriteTool._current_todos = [{"content": "完成审查", "status": "pending"}]

    llm = PendingTodoLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=True,
    )
    agent.planner.current_plan = object()
    agent._todo_all_completed = False

    result = agent.run("对项目做 code review")
    assert "已生成文件" in result
    assert llm.calls == 2
    TodoWriteTool.clear()


def test_prevent_finish_for_background_progress_phrase(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    llm = BackgroundProgressLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=True,
    )
    agent.planner.current_plan = object()
    agent._todo_all_completed = False

    result = agent.run("执行集成演练")
    assert "最终报告" in result
    assert llm.calls == 2


def test_emits_assistant_decision_progress_event(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    captured = []

    def _progress(event, data):
        captured.append((event, data))

    agent = CodeMateAgent(
        llm_client=DecisionSummaryLLM(),
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
        progress_callback=_progress,
    )
    result = agent.run("给我一个下一步建议")
    assert "准备调用 task 子代理分析项目" in result
    assert any(
        event == "assistant_decision" and "准备调用 task 子代理分析项目" in data.get("summary", "")
        for event, data in captured
    )


def test_emits_runtime_warning_when_team_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("TEAM_AGENT_ENABLED", "false")
    captured = []

    def _progress(event, data):
        captured.append((event, data))

    agent = CodeMateAgent(
        llm_client=DecisionSummaryLLM(),
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
        progress_callback=_progress,
    )
    _ = agent.run("请验证 team_status 和 events.jsonl")
    assert any(event == "runtime_warning" for event, _ in captured)


def test_auto_triggers_ui_skill_by_intent(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("SKILL_AUTO_TRIGGER_ENABLED", "true")
    llm = InspectQueryLLM()
    captured = []

    def _progress(event, data):
        captured.append((event, data))

    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
        progress_callback=_progress,
    )
    result = agent.run("请帮我设计一个项目介绍网站 UI，要求响应式布局")
    assert result == "ok"
    assert any("ui-ux-pro-max" in m for m in llm.last_tool_messages)
    assert any(event == "skill_auto_selected" for event, _ in captured)


def test_can_disable_auto_skill_trigger(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("SKILL_AUTO_TRIGGER_ENABLED", "false")
    llm = InspectQueryLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )
    result = agent.run("请帮我设计一个项目介绍网站 UI，要求响应式布局")
    assert result == "ok"
    assert "执行 Skill:" not in llm.last_user_message
    assert not any("Skill:" in m for m in llm.last_tool_messages)


def test_manual_skill_command_has_priority_over_auto(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("SKILL_AUTO_TRIGGER_ENABLED", "true")
    llm = InspectQueryLLM()
    captured = []

    def _progress(event, data):
        captured.append((event, data))

    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
        progress_callback=_progress,
    )
    result = agent.run("/ui-ux-pro-max 项目介绍网站")
    assert result == "ok"
    assert any("ui-ux-pro-max" in m for m in llm.last_tool_messages)
    assert not any(event == "skill_auto_selected" for event, _ in captured)


def test_no_skill_marker_skips_auto_trigger(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("SKILL_AUTO_TRIGGER_ENABLED", "true")
    llm = InspectQueryLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )
    result = agent.run("[no-skill] 请帮我设计一个项目介绍网站 UI，要求响应式布局")
    assert result == "ok"
    assert "执行 Skill:" not in llm.last_user_message
    assert not any("Skill:" in m for m in llm.last_tool_messages)
