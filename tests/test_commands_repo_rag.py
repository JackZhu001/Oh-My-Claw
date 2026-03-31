import io

from rich.console import Console

from codemate_agent.agent.agent import CodeMateAgent
from codemate_agent.commands.handler import handle_command
from codemate_agent.persistence.memory import MemoryManager
from codemate_agent.schema import LLMResponse
from codemate_agent.ui import display


class DummyLLM:
    model = "dummy-model"

    def complete(self, messages, tools=None):
        return LLMResponse(content="ok", tool_calls=None, finish_reason="stop", usage=None)


def test_rag_command_shows_retrieved_context(tmp_path, monkeypatch):
    stream = io.StringIO()
    test_console = Console(file=stream, force_terminal=False, color_system=None)
    monkeypatch.setattr(display, "console", test_console)
    import codemate_agent.commands.handler as handler

    monkeypatch.setattr(handler, "console", test_console)

    memory = MemoryManager(tmp_path / "memory")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "codemate.md").write_text(
        "# Oh-My-Claw 项目记忆\n\n## 关键约定\n- 使用 Kubernetes 部署\n",
        encoding="utf-8",
    )
    docs_dir = workspace / "docs"
    docs_dir.mkdir()
    (docs_dir / "ops.md").write_text(
        "# 运维\n\n## Kubernetes\n生产环境运行在 Kubernetes 中。\n",
        encoding="utf-8",
    )

    agent = CodeMateAgent(
        llm_client=DummyLLM(),
        tools=[],
        workspace_dir=str(workspace),
        memory_manager=memory,
        compression_enabled=False,
        planning_enabled=False,
    )

    handle_command("/rag Kubernetes 部署", agent, memory_manager=memory)
    output = stream.getvalue()
    assert "RepoRAG 命中" in output
    assert "codemate.md" in output or "docs/ops.md" in output
    assert "注入预览" in output
