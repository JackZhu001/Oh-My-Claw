import io

from rich.console import Console

import codemate_agent.logging.metrics as metrics_module
from codemate_agent.logging.metrics import SessionMetrics


def test_metrics_print_summary_renders_sections(monkeypatch):
    stream = io.StringIO()
    test_console = Console(file=stream, force_terminal=False, color_system=None)
    monkeypatch.setattr(metrics_module, "Console", lambda: test_console)

    metrics = SessionMetrics(session_id="s-test", model="MiniMax-M2")
    metrics.input_tokens = 1200
    metrics.output_tokens = 300
    metrics.total_tokens = 1500
    metrics.estimated_cost = 0.12
    metrics.total_rounds = 4
    metrics.llm_calls = 2
    metrics.tool_calls.record_call("read_file", success=True)
    metrics.tool_calls.record_call("write_file", success=False)
    metrics.errors = 1

    metrics.print_summary()

    output = stream.getvalue()
    assert "Session" in output
    assert "Usage" in output
    assert "Execution" in output
    assert "Tool Breakdown" in output
    assert "write_file" in output
