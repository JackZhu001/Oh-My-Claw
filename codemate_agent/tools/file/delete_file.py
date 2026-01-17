"""
删除文件工具

安全地删除文件，带有多重保护机制。
"""

from pathlib import Path
from codemate_agent.tools.base import Tool


class DeleteFileTool(Tool):
    """
    删除文件工具

    提供安全的文件删除功能，防止误删重要文件。
    """

    # 受保护的路径（不能删除）
    PROTECTED_PATHS = {
        ".git",
        ".gitignore",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        ".env.example",
        "pyproject.toml",
        "requirements.txt",
    }

    # 大文件警告阈值（10MB）
    MAX_SIZE = 10 * 1024 * 1024

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return """安全地删除文件。

参数:
- file_path: 要删除的文件路径
- confirm: 确认删除（必须设置为 true 才能执行）

安全特性:
- 只能删除工作目录内的文件
- 不能删除受保护的文件（.git, __pycache__ 等）
- 不能删除目录
- 大文件会发出警告
- 必须显式设置 confirm=true

注意: 此操作不可逆，请谨慎使用！"""

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要删除的文件路径（相对或绝对路径）"
                },
                "confirm": {
                    "type": "boolean",
                    "description": "确认删除，必须设置为 true 才能执行"
                }
            },
            "required": ["file_path", "confirm"]
        }

    def run(self, file_path: str, confirm: bool = False, **kwargs) -> str:
        """
        执行文件删除

        Args:
            file_path: 要删除的文件路径
            confirm: 确认标志

        Returns:
            str: 操作结果

        检查顺序：
        1. 先检查文件是否存在、路径是否合法等
        2. 所有检查通过后，最后才检查 confirm
        3. 这样避免让用户确认一个无法执行的操作
        """
        # 1. 解析路径
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path

        # 2. 检查文件是否存在（先检查，避免无效确认）
        if not path.exists():
            return f"错误: 文件不存在: {file_path}"

        # 3. 检查是否在工作目录内
        cwd = Path.cwd().resolve()
        try:
            path.resolve().relative_to(cwd)
        except ValueError:
            return f"错误: 只能删除工作目录内的文件。目标路径: {path}"

        # 4. 检查是否是目录
        if path.is_dir():
            return (f"错误: 不能删除目录 '{file_path}'。\n"
                    f"如需删除目录，请使用 run_shell 执行 'rm -r {file_path}'")

        # 5. 检查是否在保护列表中
        path_str = str(path)
        for protected in self.PROTECTED_PATHS:
            if protected in path_str:
                return f"错误: '{file_path}' 包含受保护的路径 '{protected}'，拒绝删除"

        # 6. 检查文件大小
        try:
            file_size = path.stat().st_size
            if file_size > self.MAX_SIZE:
                size_mb = file_size / (1024 * 1024)
                return (f"警告: 文件较大 ({size_mb:.1f}MB)。\n"
                        f"请确认确实要删除，然后使用 run_shell 执行 'rm {file_path}'")
        except Exception:
            pass  # 无法获取大小，继续

        # 7. 所有检查通过后，最后检查 confirm
        if not confirm:
            return "错误: 需要设置 confirm=true 才能删除文件。这是安全措施，防止误删。"

        # 8. 执行删除
        try:
            path.unlink()
            return f"✓ 已删除文件: {file_path}"

        except PermissionError:
            return f"错误: 权限不足，无法删除文件: {file_path}"

        except Exception as e:
            return f"错误: 删除文件失败: {e}"
