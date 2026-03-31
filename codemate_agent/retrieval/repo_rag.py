"""
RepoRAG - retrieve repository knowledge snippets for the current query.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bm25 import bm25_rank, tokenize_text

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    source: str
    title: str
    path: str
    content: str
    score: float


@dataclass
class RetrievedContext:
    query: str
    chunks: list[RetrievedChunk]
    total_chars: int

    def is_empty(self) -> bool:
        return not self.chunks

    @property
    def source_count(self) -> int:
        return len({chunk.path or chunk.source for chunk in self.chunks})

    @property
    def paths(self) -> list[str]:
        return [chunk.path or chunk.source for chunk in self.chunks]

    def to_prompt_text(self) -> str:
        if not self.chunks:
            return ""

        parts = []
        for chunk in self.chunks:
            label = chunk.path or chunk.source
            parts.append(f"### {chunk.title} ({label})\n{chunk.content}")
        return "# RepoRAG 项目上下文\n\n" + "\n\n---\n\n".join(parts)


class RepoRAG:
    """Query-aware retrieval over repo docs and long-term memory."""

    _TOP_LEVEL_MD_DENYLIST = {
        "CODE_REVIEW_CC_LOG.md",
    }
    _DEFAULT_CODE_ROOTS = (".",)
    _DEFAULT_CODE_EXTENSIONS = (
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".sh",
    )
    _CODE_DIR_DENYLIST = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".worktrees",
    }

    def __init__(
        self,
        *,
        workspace_dir: Path,
        memory_manager: Any | None = None,
        top_k: int = 5,
        char_budget: int = 2500,
        per_source_limit: int = 2,
    ) -> None:
        self.workspace_dir = Path(workspace_dir)
        self.memory_manager = memory_manager
        self.top_k = max(1, top_k)
        self.char_budget = max(500, char_budget)
        self.per_source_limit = max(1, per_source_limit)
        self.code_enabled = os.getenv("REPO_RAG_CODE_ENABLED", "true").lower() == "true"
        self.code_roots = tuple(
            self._parse_csv_env("REPO_RAG_CODE_ROOTS", self._DEFAULT_CODE_ROOTS)
        )
        self.code_extensions = {
            ext if ext.startswith(".") else f".{ext}"
            for ext in self._parse_csv_env("REPO_RAG_CODE_EXTENSIONS", self._DEFAULT_CODE_EXTENSIONS)
        }
        self.code_max_files = max(
            0,
            self._parse_int_env("REPO_RAG_CODE_MAX_FILES", 180),
        )
        self.code_max_file_bytes = max(
            1024,
            self._parse_int_env("REPO_RAG_CODE_MAX_FILE_BYTES", 200_000),
        )

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievedContext:
        query = (query or "").strip()
        if not query:
            return RetrievedContext(query=query, chunks=[], total_chars=0)

        documents = self._build_documents()
        if not documents:
            return RetrievedContext(query=query, chunks=[], total_chars=0)

        query_tokens = tokenize_text(query)
        if not query_tokens:
            return RetrievedContext(query=query, chunks=[], total_chars=0)

        scored = bm25_rank(documents, query_tokens)
        selected_docs = self._select_documents(scored, top_k=top_k or self.top_k)
        chunks = [
            RetrievedChunk(
                source=doc["source"],
                title=doc["title"],
                path=doc.get("path", ""),
                content=doc["content"],
                score=score,
            )
            for doc, score in selected_docs
        ]
        total_chars = sum(len(chunk.content) for chunk in chunks)
        return RetrievedContext(query=query, chunks=chunks, total_chars=total_chars)

    def _build_documents(self) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []

        if self.memory_manager is not None:
            get_docs = getattr(self.memory_manager, "get_memory_documents", None)
            if callable(get_docs):
                docs.extend(self._normalize_docs(get_docs()))

        docs.extend(self._load_workspace_markdown_docs())
        if self.code_enabled:
            docs.extend(self._load_workspace_code_docs())
        return docs

    def _normalize_docs(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for doc in docs:
            content = (doc.get("content") or "").strip()
            if not content:
                continue
            cloned = dict(doc)
            cloned["content"] = self._trim_chunk(content, max_chars=700)
            cloned["path"] = doc.get("path", "")
            cloned["tokens"] = tokenize_text(cloned["content"])
            normalized.append(cloned)
        return normalized

    def _load_workspace_markdown_docs(self) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for path in self._iter_markdown_candidate_paths():
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.debug("读取 RepoRAG 文档失败 %s: %s", path, exc)
                continue
            rel_path = path.relative_to(self.workspace_dir).as_posix()
            docs.extend(self._split_markdown_document(text, rel_path))
        return docs

    def _iter_markdown_candidate_paths(self) -> list[Path]:
        paths: list[Path] = []
        seen: set[Path] = set()

        for child in self.workspace_dir.iterdir():
            if not child.is_file() or child.suffix.lower() != ".md":
                continue
            if child.name in self._TOP_LEVEL_MD_DENYLIST:
                continue
            if child.name.startswith("."):
                continue
            if child not in seen:
                seen.add(child)
                paths.append(child)

        docs_dir = self.workspace_dir / "docs"
        if docs_dir.exists():
            for child in sorted(docs_dir.rglob("*.md")):
                if child.is_file() and child not in seen:
                    seen.add(child)
                    paths.append(child)

        return paths

    def _load_workspace_code_docs(self) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for path in self._iter_code_candidate_paths():
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.debug("读取 RepoRAG 代码文件失败 %s: %s", path, exc)
                continue
            rel_path = path.relative_to(self.workspace_dir).as_posix()
            docs.extend(self._split_code_document(text, rel_path))
        return docs

    def _iter_code_candidate_paths(self) -> list[Path]:
        if self.code_max_files <= 0 or not self.code_roots:
            return []

        paths: list[Path] = []
        seen: set[Path] = set()

        for root in self.code_roots:
            root_path = (self.workspace_dir / root).resolve()
            if not root_path.exists() or not root_path.is_relative_to(self.workspace_dir):
                continue
            if root_path.is_file():
                if self._is_code_file_candidate(root_path) and root_path not in seen:
                    seen.add(root_path)
                    paths.append(root_path)
                if len(paths) >= self.code_max_files:
                    break
                continue

            for dirpath, dirnames, filenames in os.walk(root_path):
                dirnames[:] = sorted(
                    [
                        name
                        for name in dirnames
                        if name not in self._CODE_DIR_DENYLIST and not name.startswith(".")
                    ]
                )
                for filename in sorted(filenames):
                    file_path = Path(dirpath) / filename
                    if file_path in seen:
                        continue
                    if not self._is_code_file_candidate(file_path):
                        continue
                    seen.add(file_path)
                    paths.append(file_path)
                    if len(paths) >= self.code_max_files:
                        return paths

        return paths

    def _is_code_file_candidate(self, path: Path) -> bool:
        if not path.is_file():
            return False
        if path.suffix.lower() not in self.code_extensions:
            return False
        try:
            if path.stat().st_size > self.code_max_file_bytes:
                return False
        except OSError:
            return False
        return True

    def _split_markdown_document(self, text: str, rel_path: str) -> list[dict[str, Any]]:
        heading_re = re.compile(r"^(#{1,3})\s+(.+)$")
        lines = text.splitlines()
        sections: list[tuple[str, list[str]]] = []
        current_title = Path(rel_path).name
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer, current_title
            content = "\n".join(buffer).strip()
            if content:
                sections.append((current_title, self._split_large_chunk(content)))
            buffer = []

        for line in lines:
            match = heading_re.match(line)
            if match:
                flush()
                current_title = match.group(2).strip()
                continue
            buffer.append(line)
        flush()

        docs: list[dict[str, Any]] = []
        for title, chunks in sections:
            for idx, chunk in enumerate(chunks, 1):
                label = title if len(chunks) == 1 else f"{title} ({idx})"
                trimmed = self._trim_chunk(chunk, max_chars=700)
                docs.append(
                    {
                        "source": rel_path,
                        "title": label,
                        "path": rel_path,
                        "content": trimmed,
                        "tokens": tokenize_text(trimmed),
                    }
                )

        if docs:
            return docs

        content = self._trim_chunk(text.strip(), max_chars=700)
        if not content:
            return []
        return [{
            "source": rel_path,
            "title": Path(rel_path).name,
            "path": rel_path,
            "content": content,
            "tokens": tokenize_text(content),
        }]

    def _split_code_document(self, text: str, rel_path: str) -> list[dict[str, Any]]:
        if not text.strip():
            return []

        lines = text.splitlines()
        chunk_lines = 60
        docs: list[dict[str, Any]] = []

        for start in range(0, len(lines), chunk_lines):
            block = lines[start:start + chunk_lines]
            if not block:
                continue
            block_text = "\n".join(block).strip()
            if not block_text:
                continue
            start_line = start + 1
            end_line = start + len(block)
            chunks = self._split_large_chunk(block_text, max_chars=900)
            for idx, chunk in enumerate(chunks, 1):
                chunk_title = f"{Path(rel_path).name}:{start_line}-{end_line}"
                if len(chunks) > 1:
                    chunk_title = f"{chunk_title} ({idx})"
                trimmed = self._trim_chunk(chunk, max_chars=700)
                docs.append(
                    {
                        "source": rel_path,
                        "title": chunk_title,
                        "path": rel_path,
                        "content": trimmed,
                        "tokens": tokenize_text(trimmed),
                    }
                )

        return docs

    def _parse_csv_env(self, key: str, default_values: tuple[str, ...]) -> list[str]:
        raw = os.getenv(key, "")
        if not raw.strip():
            return [item for item in default_values if item]
        parts = [part.strip() for part in raw.split(",")]
        return [part for part in parts if part]

    def _parse_int_env(self, key: str, default_value: int) -> int:
        raw = os.getenv(key, "").strip()
        if not raw:
            return default_value
        try:
            return int(raw)
        except ValueError:
            logger.warning("环境变量 %s=%r 不是整数，回退默认值 %s", key, raw, default_value)
            return default_value

    def _split_large_chunk(self, content: str, max_chars: int = 900) -> list[str]:
        content = content.strip()
        if len(content) <= max_chars:
            return [content]

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
        if not paragraphs:
            return [content[:max_chars]]

        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = paragraph
        if current:
            chunks.append(current)
        return chunks or [content[:max_chars]]

    def _trim_chunk(self, content: str, *, max_chars: int) -> str:
        content = content.strip()
        if len(content) <= max_chars:
            return content
        return content[: max_chars - 3].rstrip() + "..."

    def _select_documents(
        self,
        scored_docs: list[tuple[dict[str, Any], float]],
        *,
        top_k: int,
    ) -> list[tuple[dict[str, Any], float]]:
        selected: list[tuple[dict[str, Any], float]] = []
        by_source: dict[str, int] = {}
        used_chars = 0

        for doc, score in scored_docs:
            if score <= 0:
                continue

            source = doc.get("source", "")
            if by_source.get(source, 0) >= self.per_source_limit:
                continue

            content = doc.get("content", "")
            if not content:
                continue

            remaining = self.char_budget - used_chars
            if remaining <= 0:
                break

            if len(content) > remaining:
                if remaining < 120:
                    continue
                doc = dict(doc)
                doc["content"] = self._trim_chunk(content, max_chars=remaining)
                doc["tokens"] = tokenize_text(doc["content"])
                content = doc["content"]

            selected.append((doc, score))
            by_source[source] = by_source.get(source, 0) + 1
            used_chars += len(content)

            if len(selected) >= top_k:
                break

        return selected
