import io

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
