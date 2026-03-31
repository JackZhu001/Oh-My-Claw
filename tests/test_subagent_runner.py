from codemate_agent.schema import ToolCall
from codemate_agent.tools.file.write_file import WriteFileTool
from codemate_agent.tools.registry import ToolRegistry
from codemate_agent.tools.task.subagent_runner import SubagentRunner


class DummyLLM:
    model = "dummy"

    def complete(self, messages, tools=None):  # pragma: no cover - not used in these tests
        raise AssertionError("llm.complete should not be called")


def _build_registry(tmp_path):
    registry = ToolRegistry()
    registry.register(WriteFileTool(workspace_dir=str(tmp_path)))
    return registry


def test_subagent_runner_default_denied_blocks_write_tools(tmp_path):
    runner = SubagentRunner(
        llm_client=DummyLLM(),
        tool_registry=_build_registry(tmp_path),
    )
    assert "write_file" not in runner.tool_registry.list_tools()


def test_subagent_runner_explicit_allowed_tools_does_not_apply_default_denied(tmp_path):
    runner = SubagentRunner(
        llm_client=DummyLLM(),
        tool_registry=_build_registry(tmp_path),
        allowed_tools={"write_file"},
        denied_tools=None,
    )
    assert "write_file" in runner.tool_registry.list_tools()


def test_subagent_runner_normalizes_long_write_into_chunks(tmp_path):
    runner = SubagentRunner(
        llm_client=DummyLLM(),
        tool_registry=_build_registry(tmp_path),
        allowed_tools={"write_file", "write_file_chunks"},
        denied_tools=None,
    )
    tool_name, args = runner._normalize_file_write_call(  # noqa: SLF001 - internal behavior contract
        "write_file",
        {"file_path": "docs/welcome.html", "content": "a" * 4000},
    )
    assert tool_name == "write_file_chunks"
    assert args["file_path"] == "docs/welcome.html"
    assert isinstance(args["chunks"], list)
    assert len(args["chunks"]) >= 2


def test_subagent_runner_write_failover_hint_after_two_param_failures(tmp_path):
    runner = SubagentRunner(
        llm_client=DummyLLM(),
        tool_registry=_build_registry(tmp_path),
        allowed_tools={"write_file_chunks"},
        denied_tools=None,
    )
    call = ToolCall(
        id="t1",
        function={"name": "write_file_chunks", "arguments": {}},
    )
    first = runner._execute_tool_call(call)  # noqa: SLF001 - internal behavior contract
    second = runner._execute_tool_call(call)  # noqa: SLF001 - internal behavior contract

    assert "参数错误" in first
    assert "写文件工具已连续失败2次" in second
