from codemate_agent.agent.agent import CodeMateAgent
from codemate_agent.llm.client import ToolProtocolError
from codemate_agent.schema import LLMResponse, ToolCall, FunctionCall, Message
from codemate_agent.tools.file.append_file import AppendFileTool
from codemate_agent.tools.file.append_file_chunks import AppendFileChunksTool
from codemate_agent.tools.todo.todo_write import TodoWriteTool
from codemate_agent.tools.file.write_file import WriteFileTool
from codemate_agent.tools.file.write_file_chunks import WriteFileChunksTool


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


class SearchMoreProgressLLM:
    model = "dummy-model"

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="让我搜索更多关于 AI Coding Agent 竞品的详细信息。",
                tool_calls=None,
                finish_reason="stop",
                usage=None,
            )
        return LLMResponse(
            content="已生成文件：docs/welcome.html",
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


class StrictCompletionGateLLM:
    model = "dummy-model"

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None):
        self.calls += 1
        return LLMResponse(
            content="已完成全部内容，准备给最终答案。",
            tool_calls=None,
            finish_reason="stop",
            usage=None,
        )


class TransientErrorThenSuccessLLM:
    model = "dummy-model"

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError(
                "LLM API 调用失败: Error code: 500 - {'type': 'error', 'error': {'type': 'server_error', 'message': 'unknown error, 520 (1000)', 'http_code': '500'}}"
            )
        return LLMResponse(
            content="恢复成功，任务继续执行。",
            tool_calls=None,
            finish_reason="stop",
            usage=None,
        )


class AlwaysTransientErrorLLM:
    model = "dummy-model"

    def complete(self, messages, tools=None):
        raise RuntimeError(
            "LLM API 调用失败: Error code: 500 - {'type': 'error', 'error': {'type': 'server_error', 'message': 'unknown error, 520 (1000)', 'http_code': '500'}}"
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


class ToolProtocolRepairLLM:
    model = "dummy-model"

    def __init__(self):
        self.calls = 0
        self.seen_repair_note = False
        self.has_structured_tool_messages = False

    def complete(self, messages, tools=None):
        self.calls += 1
        self.seen_repair_note = any(
            msg.role == "system" and "已将旧工具轨迹压平成纯文本继续" in (msg.content or "")
            for msg in messages
        )
        self.has_structured_tool_messages = any(msg.role == "tool" for msg in messages)
        if self.calls == 1:
            raise ToolProtocolError("tool call result does not follow tool call (2013)")
        return LLMResponse(
            content="已生成文件：docs/welcome.html",
            tool_calls=None,
            finish_reason="stop",
            usage=None,
        )


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


def test_prevent_finish_for_search_more_progress_phrase(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    llm = SearchMoreProgressLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=True,
    )
    agent.planner.current_plan = object()
    agent._todo_all_completed = False

    result = agent.run("生成新人项目介绍网页")
    assert "welcome.html" in result
    assert llm.calls == 2


def test_pending_todo_blocks_finish_even_without_current_plan(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    TodoWriteTool.clear()
    TodoWriteTool._current_summary = "site"
    TodoWriteTool._current_todos = [{"content": "写网页", "status": "pending"}]

    llm = SearchMoreProgressLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=True,
    )
    agent.planner.current_plan = None
    agent._todo_all_completed = False

    result = agent.run("生成新人项目介绍网页")
    assert "welcome.html" in result
    assert llm.calls == 2
    TodoWriteTool.clear()


def test_auto_converts_long_write_file_to_chunk_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    agent = CodeMateAgent(
        llm_client=DummyLLM(),
        tools=[
            WriteFileTool(workspace_dir=str(tmp_path)),
            WriteFileChunksTool(workspace_dir=str(tmp_path)),
        ],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )

    long_content = "<html>" + ("A" * 5000) + "</html>"
    result = agent._execute_tool_call(
        ToolCall(
            id="call_1",
            function=FunctionCall(
                name="write_file",
                arguments={"file_path": "site/index.html", "content": long_content},
            ),
        )
    )

    assert "已成功分块写入文件" in result
    assert "自动将超长 write_file 请求转换为 write_file_chunks" in result
    assert (tmp_path / "site/index.html").read_text(encoding="utf-8") == long_content


def test_auto_converts_long_append_file_to_chunk_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    target = tmp_path / "site" / "style.css"
    target.parent.mkdir(parents=True)
    target.write_text("body{}", encoding="utf-8")

    agent = CodeMateAgent(
        llm_client=DummyLLM(),
        tools=[
            AppendFileTool(workspace_dir=str(tmp_path)),
            AppendFileChunksTool(workspace_dir=str(tmp_path)),
        ],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )

    long_content = "\n" + (".card{color:#fff;}\n" * 250)
    result = agent._execute_tool_call(
        ToolCall(
            id="call_2",
            function=FunctionCall(
                name="append_file",
                arguments={"file_path": "site/style.css", "content": long_content},
            ),
        )
    )

    assert "已成功分块追加文件" in result
    assert "自动将超长 append_file 请求转换为 append_file_chunks" in result
    assert (tmp_path / "site/style.css").read_text(encoding="utf-8") == "body{}" + long_content


def test_team_strict_mode_blocks_lead_write_tools(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("TEAM_AGENT_ENABLED", "true")
    monkeypatch.setenv("TEAM_STRICT_MODE", "true")
    agent = CodeMateAgent(
        llm_client=DummyLLM(),
        tools=[
            WriteFileTool(workspace_dir=str(tmp_path)),
            WriteFileChunksTool(workspace_dir=str(tmp_path)),
        ],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )

    result = agent._execute_tool_call(
        ToolCall(
            id="call_strict_write",
            function=FunctionCall(
                name="write_file",
                arguments={"file_path": "docs/welcome.html", "content": "<h1>x</h1>"},
            ),
        )
    )

    assert "TEAM_STRICT_MODE" in result
    assert not (tmp_path / "docs" / "welcome.html").exists()


def test_team_strict_mode_blocks_final_answer_until_reviewer(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("TEAM_AGENT_ENABLED", "true")
    monkeypatch.setenv("TEAM_STRICT_MODE", "true")
    llm = StrictCompletionGateLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        max_rounds=2,
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )
    sid = agent.session_id
    assert agent.team is not None

    researcher = agent.team.task_board.create_task(
        "Collect facts",
        "docs",
        assignee="researcher",
        session_id=sid,
    )
    agent.team.task_board.update_task(
        researcher["id"],
        status="completed",
        owner="researcher",
        assignee="researcher",
    )
    builder = agent.team.task_board.create_task(
        "Build page",
        "html",
        assignee="builder",
        session_id=sid,
    )
    agent.team.task_board.update_task(
        builder["id"],
        status="completed",
        owner="builder",
        assignee="builder",
    )

    result = agent.run("给最终答案")
    assert "已达到最大轮数" in result
    assert llm.calls == 2
    assert any(
        (msg.role == "system" and "TEAM_STRICT_MODE" in (msg.content or ""))
        for msg in agent.messages
    )
    status = agent.get_team_status()
    assert status["strict_mode"] is True
    assert status["strict_progress"]["reviewer_done"] is False


def test_transient_llm_error_auto_retries_and_recovers(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("LLM_TRANSIENT_RETRY_ROUNDS", "2")
    llm = TransientErrorThenSuccessLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )

    result = agent.run("继续执行")
    assert "恢复成功" in result
    assert llm.calls == 2
    assert any(
        msg.role == "system" and "上游模型服务暂时异常" in (msg.content or "")
        for msg in agent.messages
    )


def test_transient_llm_error_soft_fails_after_retry_limit(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("LLM_TRANSIENT_RETRY_ROUNDS", "2")
    monkeypatch.setenv("LLM_TRANSIENT_SOFT_FAIL", "true")
    agent = CodeMateAgent(
        llm_client=AlwaysTransientErrorLLM(),
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )

    result = agent.run("继续执行")
    assert "上游模型服务持续异常" in result


def test_team_strict_mode_blocks_run_shell_for_lead(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("TEAM_AGENT_ENABLED", "true")
    monkeypatch.setenv("TEAM_STRICT_MODE", "true")
    agent = CodeMateAgent(
        llm_client=DummyLLM(),
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )

    result = agent._build_team_tool_intervention("run_shell")
    assert "TEAM_STRICT_MODE" in result


def test_system_prompt_includes_team_strict_mode_constraints(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    monkeypatch.setenv("TEAM_AGENT_ENABLED", "true")
    monkeypatch.setenv("TEAM_STRICT_MODE", "true")
    agent = CodeMateAgent(
        llm_client=DummyLLM(),
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )
    system_prompt = agent.messages[0].content
    assert "TEAM_STRICT_MODE 约束" in system_prompt
    assert "researcher（调研）-> builder（实现）-> reviewer（验收）" in system_prompt


def test_repair_tool_protocol_history_and_retry(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    llm = ToolProtocolRepairLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=False,
    )
    agent.messages.extend([
        Message(
            role="assistant",
            content="",
            tool_calls=[{"id": "c1", "type": "function", "function": {"name": "write_file", "arguments": {"file_path": "a.txt"}}}],
        ),
        Message(role="tool", content="已成功写入文件: a.txt", tool_call_id="c1", name="write_file"),
    ])

    result = agent.run("继续生成网页")
    assert "welcome.html" in result
    assert llm.calls == 2
    assert llm.seen_repair_note is True
    assert llm.has_structured_tool_messages is False


def test_tool_protocol_residue_not_treated_as_final(monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_ENABLED", "false")
    llm = ToolProtocolRepairLLM()
    agent = CodeMateAgent(
        llm_client=llm,
        tools=[],
        workspace_dir=str(tmp_path),
        compression_enabled=False,
        planning_enabled=True,
    )
    agent.planner.current_plan = object()
    agent._todo_all_completed = False

    assert agent._is_non_final_progress_response(
        "第一部分已写入成功。\n[append_file output]\n[tool _ {file_path: \"project-intro/index.html\"}]</tool_call>"
    ) is True


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
    assert any(
        event == "tool_call_start" and data.get("tool") == "skill"
        for event, data in captured
    )
    assert any(
        event == "tool_call_end" and data.get("tool") == "skill" and data.get("success") is True
        for event, data in captured
    )


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
    assert any(
        event == "tool_call_start" and data.get("tool") == "skill"
        for event, data in captured
    )


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
