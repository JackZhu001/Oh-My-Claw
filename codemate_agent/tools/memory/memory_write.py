"""
Memory Write 工具 - 主动写入长期记忆

Agent 通过此工具在对话过程中将重要信息持久化到长期记忆，
供后续会话检索和使用。

触发时机：
1. 用户明确表达偏好（"以后用 X"、"记住 Y"）
2. 从代码/配置确认了项目约定
3. 发现值得长期保留的结论或 Bug 记录
"""

from datetime import datetime
from typing import Any, ClassVar, Dict, Literal, Optional

from codemate_agent.tools.base import Tool

# 去重：关键词重叠率超过此阈值视为重复，跳过写入
_DEDUP_OVERLAP_THRESHOLD = 0.80
# 最短关键词长度（过滤"的"、"了"等停用词效果不好的短词）
_MIN_KEYWORD_LEN = 3


# 允许的分类
VALID_CATEGORIES = {"preference", "project", "finding"}

CATEGORY_LABELS = {
    "preference": "用户偏好",
    "project": "项目约定",
    "finding": "重要发现",
}

# 每条记忆最大长度
MAX_CONTENT_LENGTH = 500


class MemoryWriteTool(Tool):
    """
    长期记忆写入工具

    将重要信息追加到对应的长期记忆文件中。
    使用 ClassVar 存储 MemoryManager 引用，由 Agent 初始化时注入。
    """

    _memory_manager: ClassVar[Optional[Any]] = None  # MemoryManager
    _workspace_dir: ClassVar[Optional[Any]] = None   # Path，用于定位 codemate.md

    @classmethod
    def set_dependencies(cls, memory_manager: Any, workspace_dir: Any = None) -> None:
        """注入 MemoryManager 依赖（由 Agent.__init__ 调用）"""
        cls._memory_manager = memory_manager
        cls._workspace_dir = workspace_dir

    @property
    def name(self) -> str:
        return "memory_write"

    @property
    def description(self) -> str:
        return """将重要信息写入长期记忆，供后续会话使用。

何时调用：
- 用户说「记住」「以后」「我们项目」等表达偏好的语句
- 从代码/配置文件确认了项目约定（如测试框架、代码风格）
- 发现重要 Bug 位置或架构结论，值得以后参考

参数：
- content: 要记住的内容（简洁，最多 500 字）
- category: 分类
  - "preference": 用户偏好（如代码风格、沟通习惯）
  - "project": 项目约定（如技术栈、目录结构、命名规范）
  - "finding": 重要发现（如已知 Bug 位置、性能瓶颈、关键决策）

不要写入：临时结果、猜测性内容、工具报错"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要记住的内容，简洁清晰，最多 500 字",
                },
                "category": {
                    "type": "string",
                    "enum": ["preference", "project", "finding"],
                    "description": "记忆分类：preference（用户偏好）/ project（项目约定）/ finding（重要发现）",
                },
            },
            "required": ["content", "category"],
        }

    def run(self, **kwargs) -> str:
        content: str = kwargs.get("content", "").strip()
        category: str = kwargs.get("category", "")

        # 参数校验
        if not content:
            return "❌ memory_write 错误：content 不能为空"

        if category not in VALID_CATEGORIES:
            return f"❌ memory_write 错误：category 必须是 {list(VALID_CATEGORIES)} 之一，收到 {category!r}"

        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH]

        if MemoryWriteTool._memory_manager is None:
            return "❌ memory_write 错误：MemoryManager 未初始化（请确认记忆功能已启用）"

        try:
            # 去重检查：避免重复写入相似内容
            existing = self._load_target_file(category)
            if existing and self._is_duplicate(content, existing):
                return f"⏭️ 跳过写入（内容与已有记忆高度重叠）：{content[:80]}{'...' if len(content) > 80 else ''}"

            self._append_to_memory(content, category)
            label = CATEGORY_LABELS[category]
            return f"✅ 已写入长期记忆（{label}）：{content[:80]}{'...' if len(content) > 80 else ''}"
        except Exception as e:
            return f"❌ memory_write 写入失败：{e}"

    def _load_target_file(self, category: str) -> str:
        """加载写入目标文件的当前内容（用于去重检查）"""
        mm = MemoryWriteTool._memory_manager
        if category == "preference":
            return mm.load_user_preferences()
        elif category == "finding":
            return mm.load_custom_memory()
        elif category == "project":
            workspace = MemoryWriteTool._workspace_dir
            if workspace is not None:
                from pathlib import Path
                codemate_path = Path(workspace) / "codemate.md"
                if codemate_path.exists():
                    return mm.load_codemate_file(Path(workspace))
            return mm.load_custom_memory()
        return ""

    @staticmethod
    def _is_duplicate(new_content: str, existing: str) -> bool:
        """检查 new_content 的关键词是否已大量出现在 existing 中。"""
        keywords = {
            w for w in new_content.replace("，", " ").replace("。", " ").split()
            if len(w) >= _MIN_KEYWORD_LEN
        }
        if not keywords:
            return False
        overlap = sum(1 for kw in keywords if kw in existing)
        return overlap / len(keywords) >= _DEDUP_OVERLAP_THRESHOLD

    def _append_to_memory(self, content: str, category: str) -> None:
        """将内容追加到对应的记忆文件对应 section"""
        mm = MemoryWriteTool._memory_manager
        timestamp = datetime.now().strftime("%Y-%m-%d")
        entry = f"- [{timestamp}] {content}"

        if category == "preference":
            self._append_to_section(
                load_fn=mm.load_user_preferences,
                save_fn=mm.save_user_preferences,
                section_header="## 自动记录",
                entry=entry,
            )
        elif category == "project":
            self._append_to_project_codemate(mm, entry)
        elif category == "finding":
            self._append_to_section(
                load_fn=mm.load_custom_memory,
                save_fn=mm.save_custom_memory,
                section_header="## 重要发现",
                entry=entry,
            )

    def _append_to_section(
        self,
        load_fn,
        save_fn,
        section_header: str,
        entry: str,
    ) -> None:
        """在文件中找到指定 section 并追加，若不存在则在末尾新建"""
        content = load_fn()
        lines = content.splitlines()

        # 找到 section 的插入位置
        insert_idx = None
        for i, line in enumerate(lines):
            if line.strip() == section_header:
                # 找到了 section，在该 section 的最后一条 item 之后插入
                j = i + 1
                while j < len(lines) and (lines[j].startswith("-") or lines[j].strip() == ""):
                    j += 1
                insert_idx = j
                break

        if insert_idx is not None:
            lines.insert(insert_idx, entry)
        else:
            # section 不存在，追加到文件末尾
            lines.append("")
            lines.append(section_header)
            lines.append(entry)

        save_fn("\n".join(lines) + "\n")

    def _append_to_project_codemate(self, mm: Any, entry: str) -> None:
        """项目约定写入 codemate.md 的 '## 关键约定' section。
        若 codemate.md 不存在或 workspace_dir 未知，降级写入 custom_memory.md。
        """
        workspace = MemoryWriteTool._workspace_dir
        if workspace is not None:
            from pathlib import Path
            ws_path = Path(workspace)
            codemate_path = ws_path / "codemate.md"
            if codemate_path.exists():
                self._append_to_section(
                    load_fn=lambda: mm.load_codemate_file(ws_path),
                    save_fn=lambda content: mm.save_codemate_file(ws_path, content),
                    section_header="## 关键约定",
                    entry=entry,
                )
                return
        # 降级：codemate.md 不存在时写入 custom_memory.md
        self._append_to_section(
            load_fn=mm.load_custom_memory,
            save_fn=mm.save_custom_memory,
            section_header="## 项目约定",
            entry=entry,
        )
