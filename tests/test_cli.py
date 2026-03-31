import io
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

from codemate_agent import cli
from codemate_agent.ui import display


def test_print_cli_error_keeps_literal_brackets(monkeypatch):
    stream = io.StringIO()
    test_console = Console(file=stream, force_terminal=False, color_system=None)
    monkeypatch.setattr(cli, "console", test_console)

    cli._print_cli_error("执行出错", "closing tag '[/TOOL_CALL]' at position 24")

    output = stream.getvalue()
    assert "执行出错" in output
    assert "[/TOOL_CALL]" in output


def test_print_error_keeps_literal_brackets(monkeypatch):
    stream = io.StringIO()
    test_console = Console(file=stream, force_terminal=False, color_system=None)
    monkeypatch.setattr(display, "console", test_console)

    display.print_error("bad closing tag '[/TOOL_CALL]'")

    output = stream.getvalue()
    assert "[/TOOL_CALL]" in output


def test_canonical_confirm_response_accepts_repeated_keys():
    assert cli._canonical_confirm_response("yyyyy") == "y"
    assert cli._canonical_confirm_response("aaaa") == "a"
    assert cli._canonical_confirm_response("no") == "n"
    assert cli._canonical_confirm_response("quit") == "q"
    assert cli._canonical_confirm_response("maybe") == "maybe"


def test_should_auto_confirm_applies_to_shell_tools():
    state = {"auto_confirm": True}
    assert cli._should_auto_confirm(state, "run_shell") is True
    assert cli._should_auto_confirm(state, "background_run") is True


def test_strip_hidden_reasoning_removes_think_block():
    text = "<think>internal reasoning</think>\n\n最终答案"
    assert cli._strip_hidden_reasoning(text) == "最终答案"


def test_strip_hidden_reasoning_removes_minimax_protocol_residue():
    text = """
<think>internal reasoning</think>
<minimax:tool_call>
<invoke name="read_file">
<parameter name="file_path">README.md</parameter>
</invoke>
</minimax:tool_call>

最终答案
"""
    assert cli._strip_hidden_reasoning(text) == "最终答案"


def test_strip_hidden_reasoning_removes_bracket_tool_protocol_residue():
    text = """
[tool_call]
[invoke name="read_file"]
[parameter name="file_path"]README.md[/parameter]
[/invoke]
[/tool_call]

最终答案
"""
    assert cli._strip_hidden_reasoning(text) == "最终答案"


def test_plain_panel_renders_literal_tool_call_tags():
    panel = cli._plain_panel("hello [/tool_call]", title="答案", border_style="green")

    assert isinstance(panel.renderable, cli.Text)
    assert str(panel.renderable) == "hello [/tool_call]"


def test_find_existing_artifacts_detects_real_files(tmp_path):
    target = tmp_path / "docs" / "welcome.html"
    target.parent.mkdir()
    target.write_text("<html></html>", encoding="utf-8")

    found = cli._find_existing_artifacts("已生成 `docs/welcome.html`", tmp_path)
    assert found == [target.resolve()]


def test_find_existing_artifacts_ignores_reference_files_without_creation_context(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("# readme", encoding="utf-8")

    found = cli._find_existing_artifacts("参考 README.md 和 PROJECT_REPORT.md", tmp_path)
    assert found == []


def test_print_startup_summary_shows_capabilities(monkeypatch, tmp_path):
    stream = io.StringIO()
    test_console = Console(file=stream, force_terminal=False, color_system=None)
    monkeypatch.setattr(display, "console", test_console)

    cfg = SimpleNamespace(
        model="MiniMax-M2",
        max_rounds=50,
        cwd=tmp_path,
        api_provider="minimax",
        log_level="INFO",
        trace_enabled=True,
        metrics_enabled=True,
        persistence_enabled=True,
        repo_rag_enabled=True,
    )
    display.print_startup_summary(cfg)

    output = stream.getvalue()
    assert "Runtime" in output
    assert "Capabilities" in output
    assert "RepoRAG" in output
