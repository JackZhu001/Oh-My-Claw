"""
长期记忆管理 - 跨会话的持久化记忆

管理用户偏好、项目上下文等长期信息。
"""

from pathlib import Path
from typing import Optional


class MemoryManager:
    """
    长期记忆管理器

    存储和检索跨会话的持久化信息。
    """

    # 记忆文件名
    USER_PREFERENCES = "user_preferences.md"
    PROJECT_CONTEXT = "project_context.md"
    CODE_SNIPPETS = "code_snippets.md"
    CUSTOM_MEMORY = "custom_memory.md"

    def __init__(self, memory_dir: Path):
        """
        初始化 MemoryManager

        Args:
            memory_dir: 记忆存储目录
        """
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # 初始化默认记忆文件
        self._init_default_files()

    def _init_default_files(self) -> None:
        """初始化默认的记忆文件"""
        # 用户偏好
        if not (self.memory_dir / self.USER_PREFERENCES).exists():
            self.save_user_preferences(self._default_user_preferences())

        # 项目上下文
        if not (self.memory_dir / self.PROJECT_CONTEXT).exists():
            self.save_project_context(self._default_project_context())

        # 代码片段
        if not (self.memory_dir / self.CODE_SNIPPETS).exists():
            self.save_code_snippets(self._default_code_snippets())

    def _default_user_preferences(self) -> str:
        """默认用户偏好模板"""
        return """# 用户偏好

> 此文件记录您的使用偏好，帮助 Agent 更好地为您服务。

## 编码风格
- （示例）使用 4 空格缩进
- （示例）变量命名用 snake_case

## 沟通风格
- （示例）回答要简洁，不要啰嗦
- （示例）优先给出代码，少解释原理

## 项目约定
- （示例）测试文件命名以 test_ 开头
- （示例）日志用 loguru 而不是 logging

## 常用模式
- （示例）写类时优先用 dataclass
"""

    def _default_project_context(self) -> str:
        """默认项目上下文模板"""
        return """# 项目上下文

> 此文件记录当前项目的背景信息。

## 项目概述
- 项目名称：
- 主要技术栈：
- 项目类型：Web 应用 / CLI 工具 / 库 / 其他

## 项目结构
```
src/
├── main.py
└── ...
```

## 重要约定
- （记录项目特定的编码约定）
"""

    def _default_code_snippets(self) -> str:
        """默认代码片段模板"""
        return """# 代码片段知识库

> 此文件记录常用的代码模式和解决方案。

## 数据处理
```python
# （示例）常用数据处理模式
```

## 错误处理
```python
# （示例）常用的错误处理模式
```
"""

    # ==================== 用户偏好 ====================

    def load_user_preferences(self) -> str:
        """加载用户偏好"""
        path = self.memory_dir / self.USER_PREFERENCES
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return self._default_user_preferences()

    def save_user_preferences(self, content: str) -> None:
        """保存用户偏好"""
        path = self.memory_dir / self.USER_PREFERENCES
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def update_user_preference(self, key: str, value: str) -> None:
        """
        更新单个用户偏好

        Args:
            key: 偏好键（如 "编码风格"）
            value: 偏好值
        """
        content = self.load_user_preferences()
        lines = content.split("\n")

        # 查找并更新
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"## {key}") or line.strip().startswith(f"- {key}"):
                # 找到位置，在下一行添加
                lines.insert(i + 1, f"- {value}")
                updated = True
                break

        if not updated:
            # 没找到，添加到对应分类或末尾
            lines.append(f"\n## {key}\n- {value}")

        self.save_user_preferences("\n".join(lines))

    # ==================== 项目上下文 ====================

    def load_project_context(self) -> str:
        """加载项目上下文"""
        path = self.memory_dir / self.PROJECT_CONTEXT
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return self._default_project_context()

    def save_project_context(self, content: str) -> None:
        """保存项目上下文"""
        path = self.memory_dir / self.PROJECT_CONTEXT
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # ==================== 代码片段 ====================

    def load_code_snippets(self) -> str:
        """加载代码片段"""
        path = self.memory_dir / self.CODE_SNIPPETS
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return self._default_code_snippets()

    def save_code_snippets(self, content: str) -> None:
        """保存代码片段"""
        path = self.memory_dir / self.CODE_SNIPPETS
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # ==================== 自定义记忆 ====================

    def load_custom_memory(self) -> str:
        """加载自定义记忆"""
        path = self.memory_dir / self.CUSTOM_MEMORY
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return "# 自定义记忆\n\n> 在此添加任何您希望 Agent 记住的信息。\n"

    def save_custom_memory(self, content: str) -> None:
        """保存自定义记忆"""
        path = self.memory_dir / self.CUSTOM_MEMORY
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # ==================== 组合加载 ====================

    def load_all_memory(self) -> str:
        """
        加载所有记忆内容

        Returns:
            合并后的记忆文本
        """
        parts = []

        user_prefs = self.load_user_preferences()
        if user_prefs.strip() and not user_prefs.startswith("# 用户偏好\n\n> 此文件"):
            parts.append(f"## 用户偏好\n{user_prefs}")

        project_ctx = self.load_project_context()
        if project_ctx.strip() and not project_ctx.startswith("# 项目上下文\n\n> 此文件"):
            parts.append(f"## 项目上下文\n{project_ctx}")

        code_snippets = self.load_code_snippets()
        if code_snippets.strip() and not code_snippets.startswith("# 代码片段知识库\n\n> 此文件"):
            parts.append(f"## 代码片段知识库\n{code_snippets}")

        custom = self.load_custom_memory()
        if custom.strip() and not custom.startswith("# 自定义记忆\n\n> 在此"):
            parts.append(f"## 自定义记忆\n{custom}")

        if parts:
            return "\n\n---\n\n".join(parts)

        return "# 长期记忆\n\n暂无记忆内容。"

    def get_memory_files_info(self) -> dict[str, dict]:
        """
        获取所有记忆文件的信息

        Returns:
            文件信息字典 {filename: {exists, size, path}}
        """
        files = [
            self.USER_PREFERENCES,
            self.PROJECT_CONTEXT,
            self.CODE_SNIPPETS,
            self.CUSTOM_MEMORY,
        ]

        info = {}
        for filename in files:
            path = self.memory_dir / filename
            info[filename] = {
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else 0,
                "path": str(path),
            }

        return info

    def __repr__(self) -> str:
        return f"MemoryManager(dir={self.memory_dir})"
