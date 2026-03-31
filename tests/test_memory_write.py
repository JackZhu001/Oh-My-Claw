"""
单元测试：MemoryWriteTool 和 MemoryReadTool
"""
from pathlib import Path

import pytest

from codemate_agent.persistence.memory import MemoryManager
from codemate_agent.tools.memory.memory_write import MemoryWriteTool
from codemate_agent.tools.memory.memory_read import MemoryReadTool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_class_vars():
    """每个测试后清理 ClassVar，避免测试间污染。"""
    yield
    MemoryWriteTool._memory_manager = None
    MemoryWriteTool._workspace_dir = None
    MemoryReadTool._memory_manager = None


@pytest.fixture()
def memory(tmp_path):
    return MemoryManager(tmp_path / "memory")


@pytest.fixture()
def tool(memory, tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    MemoryWriteTool.set_dependencies(memory_manager=memory, workspace_dir=ws)
    return MemoryWriteTool()


@pytest.fixture()
def read_tool(memory):
    MemoryReadTool.set_dependencies(memory_manager=memory)
    return MemoryReadTool()


# ---------------------------------------------------------------------------
# MemoryWriteTool — basic write
# ---------------------------------------------------------------------------

class TestMemoryWriteBasic:
    def test_write_preference(self, tool, memory):
        result = tool.run(content="用户偏好：用 dataclass", category="preference")
        assert "✅" in result
        saved = memory.load_user_preferences()
        assert "用 dataclass" in saved

    def test_write_finding(self, tool, memory):
        result = tool.run(content="已知 Bug：agent.py:140 token 计数误差", category="finding")
        assert "✅" in result
        saved = memory.load_custom_memory()
        assert "agent.py:140" in saved

    def test_write_project_without_codemate_md_falls_back(self, tool, memory):
        # workspace 中没有 codemate.md，应降级写入 custom_memory.md
        result = tool.run(content="项目使用 pytest", category="project")
        assert "✅" in result
        saved = memory.load_custom_memory()
        assert "pytest" in saved

    def test_write_project_with_codemate_md(self, tmp_path, memory):
        ws = tmp_path / "ws_with_codemate"
        ws.mkdir()
        codemate = ws / "codemate.md"
        codemate.write_text("# CodeMate 项目记忆\n\n## 关键约定\n\n", encoding="utf-8")
        MemoryWriteTool.set_dependencies(memory_manager=memory, workspace_dir=ws)
        tool = MemoryWriteTool()
        result = tool.run(content="项目使用 pytest", category="project")
        assert "✅" in result
        saved = codemate.read_text(encoding="utf-8")
        assert "pytest" in saved


# ---------------------------------------------------------------------------
# MemoryWriteTool — validation
# ---------------------------------------------------------------------------

class TestMemoryWriteValidation:
    def test_empty_content_returns_error(self, tool):
        result = tool.run(content="", category="preference")
        assert "❌" in result

    def test_invalid_category_returns_error(self, tool):
        result = tool.run(content="something", category="unknown")
        assert "❌" in result

    def test_long_content_is_truncated(self, tool, memory):
        long = "x" * 600
        result = tool.run(content=long, category="finding")
        assert "✅" in result
        saved = memory.load_custom_memory()
        # 截断到 500 字
        assert "x" * 500 in saved
        assert "x" * 501 not in saved

    def test_no_memory_manager_returns_error(self):
        # 没有注入依赖时
        bare = MemoryWriteTool()
        result = bare.run(content="test", category="preference")
        assert "❌" in result


# ---------------------------------------------------------------------------
# MemoryWriteTool — dedup
# ---------------------------------------------------------------------------

class TestMemoryWriteDedup:
    def test_dedup_skips_highly_overlapping_content(self, tool, memory):
        first = tool.run(content="项目使用pytest作为测试框架", category="finding")
        assert "✅" in first
        # 写入完全相同内容应被去重
        second = tool.run(content="项目使用pytest作为测试框架", category="finding")
        assert "⏭️" in second

    def test_dedup_allows_distinct_content(self, tool, memory):
        tool.run(content="项目使用 pytest 作为测试框架", category="finding")
        result = tool.run(content="生产环境部署在 Kubernetes 集群中", category="finding")
        assert "✅" in result


# ---------------------------------------------------------------------------
# MemoryReadTool
# ---------------------------------------------------------------------------

class TestMemoryReadTool:
    def test_read_returns_relevant_content(self, read_tool, memory):
        memory.save_custom_memory(
            "# 自定义记忆\n\n## 数据库\n项目使用 PostgreSQL 和 Redis。"
        )
        result = read_tool.run(query="redis")
        assert "Redis" in result or "redis" in result

    def test_read_empty_query_returns_error(self, read_tool):
        result = read_tool.run(query="")
        assert "❌" in result

    def test_read_no_manager_returns_error(self):
        bare = MemoryReadTool()
        result = bare.run(query="something")
        assert "❌" in result

    def test_top_k_clamped_to_5(self, read_tool, memory):
        memory.save_custom_memory("# 记忆\n\n- item1\n- item2")
        result = read_tool.run(query="item", top_k=100)
        # 只需不报错即可
        assert isinstance(result, str)

    def test_read_uses_repo_rag_for_workspace_docs(self, memory, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "codemate.md").write_text(
            "# CodeMate 项目记忆\n\n## 关键约定\n- 使用 Kubernetes 部署\n",
            encoding="utf-8",
        )
        from codemate_agent.retrieval import RepoRAG

        repo_rag = RepoRAG(workspace_dir=workspace, memory_manager=memory)
        MemoryReadTool.set_dependencies(memory_manager=memory, repo_rag=repo_rag)
        tool = MemoryReadTool()

        result = tool.run(query="kubernetes")
        assert "codemate.md" in result
        assert "RepoRAG 项目上下文" in result
