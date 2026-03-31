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


def test_run_shell_uses_worktree_cwd_when_context_is_set(tmp_path):
    worktree = tmp_path / ".worktrees" / "task-1"
    worktree.mkdir(parents=True)
    tool = RunShellTool(workspace_dir=str(tmp_path))
    tool.set_execution_context(task_id=1, worktree_dir=str(worktree))
    result = tool.run("pwd")
    assert str(worktree.resolve()) in result


def test_run_shell_blocks_workspace_root_when_worktree_is_active(tmp_path):
    worktree = tmp_path / ".worktrees" / "task-1"
    worktree.mkdir(parents=True)
    (tmp_path / "root.txt").write_text("root")
    tool = RunShellTool(workspace_dir=str(tmp_path))
    tool.set_execution_context(task_id=1, worktree_dir=str(worktree))
    result = tool.run(f"cat {tmp_path / 'root.txt'}")
    assert "越界路径访问" in result


def test_parse_command_segments_respects_quoted_operators(tmp_path):
    tool = RunShellTool(workspace_dir=str(tmp_path))
    segments = tool._parse_command_segments('bash -lc "echo one && echo two"; echo done')
    assert segments[0][0] == "bash"
    assert segments[0][1] == "-lc"
    assert segments[0][2] == "echo one && echo two"
    assert segments[1][0] == "echo"
    assert segments[1][1] == "done"


def test_run_shell_blocks_inline_wrapper_execution(tmp_path):
    tool = RunShellTool(workspace_dir=str(tmp_path))
    result = tool.run('bash -lc "echo hello && echo world"')
    assert "inline wrapper" in result
