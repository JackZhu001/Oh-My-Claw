"""
Core team definitions for coordinator-driven execution.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TeamMember:
    """A single team member configuration."""

    agent_id: str
    role: str
    display_name: str = ""
    system_prompt: str = ""
    allowed_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    workspace_mode: str = "shared"
    model_policy: str = "main"
    temperature: Optional[float] = None
    max_turns: int = 15

    def matches_tool(self, tool_name: str) -> bool:
        if not tool_name:
            return False
        if tool_name in self.denied_tools:
            return False
        if not self.allowed_tools:
            return True
        return tool_name in self.allowed_tools


@dataclass
class TeamDefinition:
    """A collection of team members."""

    team_name: str
    members: dict[str, TeamMember] = field(default_factory=dict)

    def get_member(self, agent_id: str) -> Optional[TeamMember]:
        return self.members.get((agent_id or "").strip())

    def has_member(self, agent_id: str) -> bool:
        return self.get_member(agent_id) is not None


@dataclass
class ExecutionRequest:
    """Coordinator request for running one delegated task."""

    request_id: str
    task_id: Optional[int]
    agent_id: str
    title: str
    instructions: str
    context_summary: str = ""
    delegated_by: str = "lead"
    parent_task_id: Optional[int] = None
    artifact_dir: str = ""
    cwd: str = ""
    parent_session_id: str = ""
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        *,
        agent_id: str,
        title: str,
        instructions: str,
        context_summary: str = "",
        delegated_by: str = "lead",
        task_id: Optional[int] = None,
        parent_task_id: Optional[int] = None,
        artifact_dir: str = "",
        cwd: str = "",
        parent_session_id: str = "",
    ) -> "ExecutionRequest":
        return cls(
            request_id=uuid.uuid4().hex[:12],
            task_id=task_id,
            agent_id=(agent_id or "").strip(),
            title=(title or "").strip(),
            instructions=(instructions or "").strip(),
            context_summary=(context_summary or "").strip(),
            delegated_by=(delegated_by or "").strip() or "lead",
            parent_task_id=parent_task_id,
            artifact_dir=(artifact_dir or "").strip(),
            cwd=(cwd or "").strip(),
            parent_session_id=(parent_session_id or "").strip(),
        )


@dataclass
class ExecutionResult:
    """Normalized result from delegated execution."""

    request_id: str
    task_id: Optional[int]
    agent_id: str
    status: str
    summary: str
    artifact_paths: list[str] = field(default_factory=list)
    artifact_manifest_path: str = ""
    session_id: str = ""
    error: str = ""
    tool_usage: dict[str, int] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    finished_at: float = field(default_factory=time.time)

    @property
    def success(self) -> bool:
        return self.status == "completed"

    @property
    def duration_ms(self) -> int:
        return int(max(0.0, self.finished_at - self.started_at) * 1000)


def normalize_cwd(cwd: str, fallback: Path) -> Path:
    raw = (cwd or "").strip()
    if not raw:
        return Path(fallback).resolve()
    return Path(raw).resolve()
