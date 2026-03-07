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
from typing import List
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
    _SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")

    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()
        self.allowed_commands = self._load_allowlist()

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

    def _parse_command_segments(self, command: str) -> List[List[str]]:
        segments: List[List[str]] = []
        for raw_part in self._SEGMENT_SPLIT.split(command):
            part = raw_part.strip()
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

    def _is_path_escape(self, tokens: List[str]) -> bool:
        for token in tokens[1:]:
            value = token.strip()
            if not value:
                continue
            if value.startswith("../") or "/../" in value:
                return True
            if value.startswith("~/"):
                return True
            if value.startswith("/"):
                try:
                    Path(value).resolve().relative_to(self.workspace_dir)
                except ValueError:
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

        # 超时保护：避免模型设置过大 timeout 导致长时间卡住
        timeout = max(1, min(int(timeout), 45))

        try:
            # 执行命令
            result = subprocess.run(
                shell_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace_dir),
                # 安全限制：不使用 shell=True，避免命令注入
            )

            # 组合输出
            output = []
            if result.stdout:
                output.append(result.stdout)
            if result.stderr:
                output.append(f"[stderr]\n{result.stderr}")

            # 添加退出码
            if result.returncode != 0:
                output.append(f"\n[退出码: {result.returncode}]")

            return "\n".join(output).strip() or "命令执行完成，无输出"

        except subprocess.TimeoutExpired:
            return f"错误: 命令执行超时（超过 {timeout} 秒）"

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
