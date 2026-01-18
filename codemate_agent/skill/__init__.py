"""
Skill 系统 - 对标 Anthropic 官方实现

渐进式三层加载：
- Layer 1 (索引): name + description (~100 tokens/skill)
- Layer 2 (SKILL.md body): 核心流程 (~500 lines max)
- Layer 3 (references/scripts): 按需加载 (无限)

目录结构:
skills/
└── skill-name/
    ├── SKILL.md           # 必需：元数据 + 核心流程
    ├── references/        # 可选：参考文档（按需加载）
    │   ├── security.md
    │   └── quality.md
    └── scripts/           # 可选：可执行脚本（黑盒调用）
        └── analyze.py
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class Skill:
    """Skill 数据"""
    name: str
    description: str
    content: str  # SKILL.md body
    skill_dir: Path = None  # skill 所在目录
    references: dict[str, str] = field(default_factory=dict)  # 按需加载的 references
    
    def to_prompt(self, arguments: str = "") -> str:
        """生成注入的 prompt"""
        content = self.content
        content = content.replace("$TARGET", arguments)
        content = content.replace("$ARGUMENTS", arguments)
        content = content.replace("$DATETIME", self._get_datetime())
        return content
    
    def _get_datetime(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    
    def load_reference(self, name: str) -> Optional[str]:
        """按需加载 reference 文件"""
        if name in self.references:
            return self.references[name]
        
        if not self.skill_dir:
            return None
        
        ref_file = self.skill_dir / "references" / name
        if not ref_file.exists():
            # 尝试添加 .md 后缀
            ref_file = self.skill_dir / "references" / f"{name}.md"
        
        if ref_file.exists():
            content = ref_file.read_text(encoding="utf-8")
            self.references[name] = content
            return content
        
        return None
    
    def list_references(self) -> list[str]:
        """列出可用的 reference 文件"""
        if not self.skill_dir:
            return []
        ref_dir = self.skill_dir / "references"
        if not ref_dir.exists():
            return []
        return [f.name for f in ref_dir.glob("*.md")]
    
    def list_scripts(self) -> list[str]:
        """列出可用的 script 文件"""
        if not self.skill_dir:
            return []
        script_dir = self.skill_dir / "scripts"
        if not script_dir.exists():
            return []
        return [f.name for f in script_dir.glob("*") if f.is_file()]


class SkillManager:
    """
    Skill 管理器 - 对标 Anthropic 官方实现
    
    渐进式加载策略：
    - Layer 1 (索引): 启动时加载所有 name + description (~100 tokens/skill)
    - Layer 2 (SKILL.md): 触发后加载核心流程 (~500 lines max)
    - Layer 3 (references/scripts): 执行中按需加载 (无限)
    """
    
    def __init__(self, skills_dir: Path = None):
        self.skills_dir = skills_dir or Path(__file__).parent.parent.parent / "skills"
        self._index: dict[str, str] = {}  # name -> description
        self._skill_dirs: dict[str, Path] = {}  # name -> skill directory
        self._cache: dict[str, Skill] = {}  # 完整内容缓存
        self._build_index()
    
    def _build_index(self) -> None:
        """启动时构建索引（只读 frontmatter）"""
        if not self.skills_dir.exists():
            return
        
        # 新结构: skills/skill-name/SKILL.md
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            
            with open(skill_file, "r", encoding="utf-8") as f:
                header = f.read(1500)
            
            meta = self._parse_frontmatter(header)
            if meta.get("name"):
                name = meta["name"]
                self._index[name] = meta.get("description", "")
                self._skill_dirs[name] = skill_dir
    
    def _parse_frontmatter(self, text: str) -> dict:
        """解析 YAML frontmatter（支持多行值）"""
        match = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
        if not match:
            return {}
        
        content = match.group(1)
        result = {}
        current_key = None
        current_value = []
        
        for line in content.split("\n"):
            # 检查是否是新的 key
            if line and not line.startswith(" ") and not line.startswith("\t") and ":" in line:
                # 保存之前的 key-value
                if current_key:
                    result[current_key] = "\n".join(current_value).strip()
                
                key, value = line.split(":", 1)
                current_key = key.strip()
                value = value.strip()
                
                # 处理 YAML 多行语法 |
                if value == "|":
                    current_value = []
                else:
                    current_value = [value]
            elif current_key and (line.startswith("  ") or line.startswith("\t") or line.strip().startswith("-")):
                # 多行值的续行
                current_value.append(line.strip().lstrip("- "))
        
        # 保存最后一个 key-value
        if current_key:
            result[current_key] = "\n".join(current_value).strip()
        
        return result
    
    # ==================== 索引层 ====================
    
    def get_available_skills(self) -> list[str]:
        """获取可用 skill 列表"""
        return list(self._index.keys())
    
    def skill_exists(self, name: str) -> bool:
        """检查 skill 是否存在"""
        return name in self._index
    
    def get_system_prompt_addition(self) -> str:
        """
        返回注入 system prompt 的内容
        包含 skill 描述和触发条件，让 LLM 自动判断何时使用
        """
        if not self._index:
            return ""
        
        lines = [
            "",
            "## 可用 Skills",
            "",
            "Skills 是预定义的专业任务流程。当用户请求匹配下述触发条件时，",
            "你应该自动使用对应的 Skill 来处理任务。",
            "",
        ]
        
        for name, desc in self._index.items():
            lines.append(f"### {name}")
            lines.append(desc)
            lines.append("")
        
        lines.extend([
            "---",
            "",
            "**使用方式**: 当检测到用户意图匹配某个 Skill 时，",
            "在回复开头声明 `[使用 Skill: <skill-name>]`，然后严格按照 Skill 的步骤执行。",
            "",
        ])
        
        return "\n".join(lines)
    
    # ==================== 完整层 ====================
    
    def load(self, name: str) -> Optional[Skill]:
        """加载完整 skill 内容（执行时调用）"""
        if name in self._cache:
            return self._cache[name]
        
        if name not in self._skill_dirs:
            return None
        
        skill_dir = self._skill_dirs[name]
        skill_file = skill_dir / "SKILL.md"
        
        if not skill_file.exists():
            return None
        
        content = skill_file.read_text(encoding="utf-8")
        meta = self._parse_frontmatter(content)
        
        # 移除 frontmatter，保留正文
        content = re.sub(r'^---\n.*?\n---\n*', '', content, flags=re.DOTALL)
        
        skill = Skill(
            name=meta.get("name", name),
            description=meta.get("description", ""),
            content=content.strip(),
            skill_dir=skill_dir
        )
        
        self._cache[name] = skill
        return skill
    
    def prepare_execution(self, name: str, arguments: str = "") -> Optional[str]:
        """
        准备执行 skill，返回注入的 prompt
        
        Args:
            name: skill 名称
            arguments: 用户传入的参数
            
        Returns:
            完整的 skill prompt，或 None（如果 skill 不存在）
        """
        skill = self.load(name)
        if not skill:
            return None
        
        return skill.to_prompt(arguments)
    
    def clear_cache(self) -> None:
        """清理完整内容缓存（执行完毕后调用）"""
        self._cache.clear()
    
    def load_reference(self, skill_name: str, ref_name: str) -> Optional[str]:
        """
        按需加载 skill 的 reference 文件
        
        Args:
            skill_name: skill 名称
            ref_name: reference 文件名（可带或不带 .md 后缀）
            
        Returns:
            reference 内容，或 None
        """
        skill = self.load(skill_name)
        if not skill:
            return None
        return skill.load_reference(ref_name)
    
    def get_skill_resources(self, skill_name: str) -> dict:
        """
        获取 skill 可用的 references 和 scripts
        
        Returns:
            {"references": [...], "scripts": [...]}
        """
        skill = self.load(skill_name)
        if not skill:
            return {"references": [], "scripts": []}
        
        return {
            "references": skill.list_references(),
            "scripts": skill.list_scripts()
        }
    
    # ==================== 统计 ====================
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "skills_count": len(self._index),
            "cached_count": len(self._cache),
            "skills_dir": str(self.skills_dir),
            "available": list(self._index.keys()),
        }
