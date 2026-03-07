from pathlib import Path

from codemate_agent.tools.shell.run_shell import RunShellTool


def test_run_shell_rejects_non_allowlisted_command(tmp_path):
    tool = RunShellTool(workspace_dir=str(tmp_path))
    result = tool.run("unknown_command_abc --version")
    assert "命令不在允许列表" in result


def test_run_shell_uses_workspace_as_cwd(tmp_path):
    tool = RunShellTool(workspace_dir=str(tmp_path))
    result = tool.run("pwd")
    assert str(tmp_path.resolve()) in result


def test_run_shell_blocks_path_escape(tmp_path):
    tool = RunShellTool(workspace_dir=str(tmp_path))
    result = tool.run("cat ../outside.txt")
    assert "越界路径访问" in result
