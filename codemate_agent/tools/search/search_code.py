"""
代码内容搜索工具
"""

import re
from pathlib import Path
from typing import Optional
from codemate_agent.tools.base import Tool


class SearchCodeTool(Tool):
    """代码内容搜索工具"""

    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return """在代码中搜索关键词或正则表达式。

参数:
- pattern: 搜索模式（支持正则表达式）
- path: 搜索路径（默认当前目录）
- file_pattern: 文件过滤模式，如 *.py（可选）

输出: 匹配的文件路径、行号和内容"""

    def run(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: Optional[str] = None,
        **kwargs
    ) -> str:
        root = Path(path)
        if not root.is_absolute():
            root = Path.cwd() / root

        if not root.exists():
            return f"错误: 路径不存在: {path}"

        results = []
        ignored_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".idea", ".vscode"}

        # 确定文件扩展名过滤
        extensions = None
        if file_pattern:
            if file_pattern.startswith("*."):
                extensions = {file_pattern[1:]}
            else:
                extensions = {f".{file_pattern}"}

        # 遍历文件
        for file_path in root.rglob("*"):
            if file_path.is_dir():
                continue
            if any(ignored in file_path.parts for ignored in ignored_dirs):
                continue

            if extensions and file_path.suffix not in extensions:
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, 1):
                        try:
                            if re.search(pattern, line):
                                rel_path = file_path.relative_to(root)
                                display_line = line.rstrip("\n")[:200]
                                results.append(f"{rel_path}:{line_num}: {display_line}")
                        except re.error:
                            if pattern in line:
                                rel_path = file_path.relative_to(root)
                                display_line = line.rstrip("\n")[:200]
                                results.append(f"{rel_path}:{line_num}: {display_line}")
            except (PermissionError, UnicodeDecodeError):
                continue

        if not results:
            return f"未找到匹配 '{pattern}' 的内容"

        # 限制结果数量
        max_results = 50
        if len(results) > max_results:
            total_results = len(results)  # 保存原始数量
            results = results[:max_results]
            results.append(f"... (还有 {total_results - max_results} 条结果未显示)")

        return "\n".join(results)
