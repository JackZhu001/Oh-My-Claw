"""
Shell 命令执行工具

支持跨平台执行 shell 命令。
"""

import os
import re
import shlex
import subprocess
import platform
from pathlib import Path
from typing import List, Optional
from codemate_agent.tools.base import Tool


class RunShellTool(Tool):
    """
    Shell 命令执行工具

    用于执行系统命令，如 git, rm, mkdir, python 等。
    """

    DEFAULT_ALLOWED_COMMANDS = frozenset({
        "awk", "bash", "cat", "cp", "curl", "cut", "date", "echo", "env", "find",
        "git", "go", "grep", "head", "ls", "make", "mkdir", "mv", "node", "npm",
        "pip", "pip3", "printf", "pwd", "py", "python", "python3", "pytest", "rg",
        "rm", "sed", "sort", "tail", "touch", "tr", "uname", "uniq", "wc", "which",
        "xargs",
    })

    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()
        self.allowed_commands = self._load_allowlist()
        self._active_task_id = ""
        self._active_worktree: Optional[Path] = None

    @property
    def name(self) -> str:
        return "run_shell"

    @property
    def description(self) -> str:
        return """执行 shell 命令。

参数:
- command: 要执行的命令字符串
- timeout: 超时时间（秒），默认 30

支持的命令类型:
- Git 操作: git log, git status, git diff
- 文件操作: rm, mkdir, cp, mv
- 运行脚本: python, pytest, npm
- 系统信息: ls, pwd, uname

注意:
- 请谨慎使用具有破坏性的命令
- 仅允许执行 allowlist 中的命令（可通过 RUN_SHELL_ALLOWLIST 扩展）
- 默认在工作目录中执行，并阻止越界路径访问"""

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 shell 命令"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 30",
                    "default": 30
                }
            },
            "required": ["command"]
        }

    def _load_allowlist(self) -> set[str]:
        raw = os.getenv("RUN_SHELL_ALLOWLIST", "")
        if not raw.strip():
            return set(self.DEFAULT_ALLOWED_COMMANDS)
        return {item.strip() for item in raw.split(",") if item.strip()}

    def _split_command_parts(self, command: str) -> List[str]:
        """
        在不破坏引号内容的前提下按控制符分段。

        仅在引号外识别 `&&`、`||`、`;`、`|`、换行作为分隔符，
        避免将 `bash -lc "a && b"` 错误切裂导致引号不闭合。
        """
        parts: List[str] = []
        buf: List[str] = []
        in_single = False
        in_double = False
        escaped = False
        i = 0
        while i < len(command):
            ch = command[i]
            nxt = command[i + 1] if i + 1 < len(command) else ""

            if escaped:
                buf.append(ch)
                escaped = False
                i += 1
                continue

            if ch == "\\":
                buf.append(ch)
                escaped = True
                i += 1
                continue

            if ch == "'" and not in_double:
                in_single = not in_single
                buf.append(ch)
                i += 1
                continue

            if ch == '"' and not in_single:
                in_double = not in_double
                buf.append(ch)
                i += 1
                continue

            if not in_single and not in_double:
                if (ch == "&" and nxt == "&") or (ch == "|" and nxt == "|"):
                    part = "".join(buf).strip()
                    if part:
                        parts.append(part)
                    buf = []
                    i += 2
                    continue
                if ch in {";", "|", "\n"}:
                    part = "".join(buf).strip()
                    if part:
                        parts.append(part)
                    buf = []
                    i += 1
                    continue

            buf.append(ch)
            i += 1

        if in_single or in_double:
            raise ValueError("No closing quotation")

        last = "".join(buf).strip()
        if last:
            parts.append(last)
        return parts

    def _parse_command_segments(self, command: str) -> List[List[str]]:
        segments: List[List[str]] = []
        for part in self._split_command_parts(command):
            if not part:
                continue
            tokens = shlex.split(part)
            while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
                tokens.pop(0)
            if tokens:
                segments.append(tokens)
        return segments

    def _is_allowed_executable(self, executable: str) -> bool:
        if executable in self.allowed_commands:
            return True
        if executable.startswith("./"):
            return True
        return False

    def set_execution_context(self, task_id: Optional[int] = None, worktree_dir: Optional[str] = None) -> None:
        """设置任务执行上下文（可选 worktree 隔离）。"""
        self._active_task_id = str(task_id) if task_id is not None else ""
        if not worktree_dir:
            self._active_worktree = None
            return

        candidate = Path(worktree_dir).expanduser()
        if not candidate.is_absolute():
            candidate = (self.workspace_dir / candidate).resolve()
        else:
            candidate = candidate.resolve()

        worktree_root = (self.workspace_dir / ".worktrees").resolve()
        if not candidate.exists() or not candidate.is_dir():
            raise ValueError(f"worktree 不存在: {candidate}")
        try:
            candidate.relative_to(worktree_root)
        except ValueError as e:
            raise ValueError("worktree 必须位于工作目录的 .worktrees 子目录") from e

        self._active_worktree = candidate

    def _effective_cwd(self) -> Path:
        if self._active_worktree and self._active_worktree.exists():
            return self._active_worktree
        return self.workspace_dir

    def _allowed_roots(self) -> List[Path]:
        cwd = self._effective_cwd().resolve()
        if self._active_worktree:
            return [cwd]
        return [self.workspace_dir]

    def _is_under_allowed_roots(self, path: Path) -> bool:
        resolved = path.resolve()
        for root in self._allowed_roots():
            try:
                resolved.relative_to(root.resolve())
                return True
            except ValueError:
                continue
        return False

    def _is_path_escape(self, tokens: List[str]) -> bool:
        cwd = self._effective_cwd()
        for token in tokens[1:]:
            value = token.strip()
            if not value:
                continue
            if value.startswith("-"):
                continue
            if "://" in value:
                continue
            if value.startswith("../") or "/../" in value:
                return True
            if value.startswith("~/"):
                return True
            if value.startswith("/"):
                try:
                    Path(value).resolve()
                except ValueError:
                    return True
                if not self._is_under_allowed_roots(Path(value)):
                    return True
                continue
            if "/" in value or value.startswith("."):
                target = (cwd / value).resolve()
                if not self._is_under_allowed_roots(target):
                    return True
        return False

    def run(self, command: str, timeout: int = 30, **kwargs) -> str:
        """
        执行 shell 命令

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）

        Returns:
            str: 命令输出结果
        """
        command = (command or "").strip()
        if not command:
            return "错误: command 参数不能为空"

        # 基本安全检查
        dangerous_commands = ["rm -rf /", "rm -rf /*", "mkfs", "format", ":(){ :|:& };:"]
        if any(dangerous in command.lower() for dangerous in dangerous_commands):
            return "错误: 检测到危险命令，拒绝执行"

        # 阻止命令替换，避免绕过 allowlist
        if "$(" in command or "`" in command:
            return "错误: 不允许使用命令替换语法"

        try:
            segments = self._parse_command_segments(command)
        except ValueError as e:
            return f"错误: 命令解析失败: {e}"

        if not segments:
            return "错误: 未检测到可执行命令"

        disallowed = [tokens[0] for tokens in segments if not self._is_allowed_executable(tokens[0])]
        if disallowed:
            blocked = ", ".join(sorted(set(disallowed)))
            return (
                f"错误: 命令不在允许列表: {blocked}。"
                f"可通过 RUN_SHELL_ALLOWLIST 环境变量追加允许命令。"
            )

        if any(self._is_path_escape(tokens) for tokens in segments):
            return "错误: 检测到越界路径访问（仅允许工作目录内路径）"

        # 确定使用哪个 shell
        system = platform.system()
        if system == "Windows":
            shell_cmd = ["powershell", "-Command", command]
        else:
            # Unix/Linux/macOS 使用 bash
            shell_cmd = ["/bin/bash", "-c", command]

        # 超时保护：前台默认 45s，后台任务（内部调用）允许放宽到 300s
        background_mode = bool(kwargs.get("_background", False))
        timeout_cap = 300 if background_mode else 45
        timeout = max(1, min(int(timeout), timeout_cap))

        try:
            # 执行命令（Unix 下创建新进程组，方便超时时清理子进程）
            popen_kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self._effective_cwd()),
            )
            if platform.system() != "Windows":
                popen_kwargs["start_new_session"] = True  # 新进程组，超时可整组 kill

            proc = subprocess.Popen(shell_cmd, **popen_kwargs)

            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                # 杀整个进程组，避免僵尸子进程
                if platform.system() != "Windows":
                    try:
                        import os, signal
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except (ProcessLookupError, PermissionError, OSError):
                        proc.kill()
                else:
                    proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                return f"错误: 命令执行超时（超过 {timeout} 秒）"

            # 组合输出
            output = []
            if stdout:
                output.append(stdout)
            if stderr:
                output.append(f"[stderr]\n{stderr}")

            # 添加退出码
            if proc.returncode != 0:
                output.append(f"\n[退出码: {proc.returncode}]")

            return "\n".join(output).strip() or "命令执行完成，无输出"

        except FileNotFoundError:
            # Windows 没有 PowerShell 或 Unix 没有 bash
            if system == "Windows":
                return "错误: 未找到 PowerShell，请确保已安装"
            else:
                return "错误: 未找到 bash，请确保系统支持"

        except PermissionError:
            return f"错误: 权限不足，无法执行命令: {command}"

        except Exception as e:
            return f"错误: 执行命令失败: {e}"
