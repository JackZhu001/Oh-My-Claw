"""
Coordinator for dispatching delegated tasks to team members.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from codemate_agent.team.artifacts import ensure_artifact_dir
from codemate_agent.team.artifacts import read_manifest
from codemate_agent.team.definitions import ExecutionRequest, ExecutionResult, TeamDefinition, TeamMember
from codemate_agent.team.executor import AgentExecutor
from codemate_agent.team.protocols import RequestTracker
from codemate_agent.team.queue import DispatchQueue
from codemate_agent.team.task_board import TaskBoard
from codemate_agent.team.team_defaults import get_default_team_definition

logger = logging.getLogger(__name__)


class StrictWorkflowError(RuntimeError):
    """Raised when TEAM_STRICT_MODE workflow stage constraints are violated."""


class TeamCoordinator:
    """Minimal coordinator that routes tasks to independent member executors."""

    def __init__(
        self,
        *,
        workspace_dir: Path,
        main_llm_client,
        tool_registry,
        light_llm_client=None,
        team_definition: Optional[TeamDefinition] = None,
        task_board: Optional[TaskBoard] = None,
        request_tracker: Optional[RequestTracker] = None,
    ) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        self.team_definition = team_definition or get_default_team_definition()
        self.task_board = task_board or TaskBoard(self.workspace_dir / ".tasks")
        self.request_tracker = request_tracker
        self.strict_mode = os.getenv("TEAM_STRICT_MODE", "false").lower() == "true"
        self.queue = DispatchQueue(
            global_limit=int(os.getenv("TEAM_GLOBAL_MAX_CONCURRENCY", "2")),
            per_agent_serial=os.getenv("TEAM_PER_AGENT_SERIAL", "true").lower() == "true",
            per_workspace_serial=os.getenv("TEAM_PER_WORKSPACE_SERIAL", "true").lower() == "true",
        )
        self.executor = AgentExecutor(
            main_llm_client=main_llm_client,
            light_llm_client=light_llm_client,
            tool_registry=tool_registry,
            workspace_dir=self.workspace_dir,
        )

    def get_member(self, agent_id: str) -> Optional[TeamMember]:
        return self.team_definition.get_member(agent_id)

    def dispatch_to(
        self,
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
    ) -> ExecutionResult:
        request = ExecutionRequest.create(
            agent_id=agent_id,
            title=title,
            instructions=instructions,
            context_summary=context_summary,
            delegated_by=delegated_by,
            task_id=task_id,
            parent_task_id=parent_task_id,
            artifact_dir=artifact_dir,
            cwd=cwd or str(self.workspace_dir),
            parent_session_id=parent_session_id,
        )
        return self.dispatch(request)

    def dispatch(self, request: ExecutionRequest) -> ExecutionResult:
        member = self.get_member(request.agent_id)
        if member is None:
            raise ValueError(f"unknown team member: {request.agent_id}")
        self._validate_strict_sequence(request, member)

        correlation_id = request.request_id or uuid.uuid4().hex[:12]
        if self.request_tracker is not None:
            self.request_tracker.create_request(
                "delegate",
                sender=request.delegated_by,
                target=member.agent_id,
                payload={"title": request.title},
                request_id=request.request_id,
                task_id=request.task_id,
                session_id=request.parent_session_id,
                correlation_id=correlation_id,
            )
            if (member.role or "").strip().lower() == "reviewer":
                self.request_tracker.create_request(
                    "review",
                    sender=request.delegated_by,
                    target=member.agent_id,
                    payload={"title": request.title},
                    request_id=request.request_id,
                    task_id=request.task_id,
                    session_id=request.parent_session_id,
                    correlation_id=correlation_id,
                )

        board_task = None
        if request.task_id is None:
            board_task = self.task_board.create_task(
                subject=request.title,
                description=request.instructions,
                assignee=member.agent_id,
                delegated_by=request.delegated_by,
                parent_task_id=request.parent_task_id,
                artifact_dir=request.artifact_dir,
                correlation_id=correlation_id,
                request_id=request.request_id,
                session_id=request.parent_session_id,
            )
            request.task_id = int(board_task["id"])
        if not request.artifact_dir:
            request.artifact_dir = str(ensure_artifact_dir(self.workspace_dir, request.task_id))
        self.task_board.update_task(
            request.task_id,
            status="in_progress",
            owner=member.agent_id,
            assignee=member.agent_id,
            delegated_by=request.delegated_by,
            parent_task_id=request.parent_task_id,
            artifact_dir=request.artifact_dir,
            correlation_id=correlation_id,
            request_id=request.request_id,
            session_id=request.parent_session_id,
        )
        self.task_board.renew_lease(request.task_id, member.agent_id, lease_ttl_sec=600)

        workspace_key = str(Path(request.cwd or self.workspace_dir).resolve())
        with self.queue.acquire(agent_id=member.agent_id, workspace_key=workspace_key):
            result = self.executor.execute(request, member)
        if result.success:
            self.task_board.update_task(
                request.task_id,
                status="completed",
                owner=member.agent_id,
                artifact_manifest=result.artifact_manifest_path,
            )
            if self.request_tracker is not None:
                self.request_tracker.update_request(
                    "delegate",
                    request_id=request.request_id,
                    status="completed",
                    responder=member.agent_id,
                    task_id=request.task_id,
                    session_id=result.session_id,
                    correlation_id=correlation_id,
                )
                self.request_tracker.update_request(
                    "artifact",
                    request_id=request.request_id,
                    status="completed",
                    responder=member.agent_id,
                    payload=read_manifest(Path(result.artifact_manifest_path)),
                    create_if_missing=True,
                    task_id=request.task_id,
                    session_id=result.session_id,
                    correlation_id=correlation_id,
                )
                if (member.role or "").strip().lower() == "reviewer":
                    self.request_tracker.update_request(
                        "review",
                        request_id=request.request_id,
                        status="approved",
                        responder=member.agent_id,
                        reason=result.summary,
                        payload={"status": "approved"},
                        create_if_missing=True,
                        task_id=request.task_id,
                        session_id=result.session_id,
                        correlation_id=correlation_id,
                    )
        else:
            failed = self.task_board.mark_failed(
                request.task_id,
                owner=member.agent_id,
                reason=result.error or result.summary,
                retryable=True,
            )
            task_state = failed or {}
            status = "failed" if task_state.get("status") == "failed" else "pending"
            if self.request_tracker is not None:
                self.request_tracker.update_request(
                    "delegate",
                    request_id=request.request_id,
                    status="failed" if status == "failed" else "pending",
                    responder=member.agent_id,
                    reason=result.error or result.summary,
                    task_id=request.task_id,
                    session_id=result.session_id,
                    correlation_id=correlation_id,
                )
                if (member.role or "").strip().lower() == "reviewer":
                    self.request_tracker.update_request(
                        "review",
                        request_id=request.request_id,
                        status="rejected",
                        responder=member.agent_id,
                        reason=result.error or result.summary,
                        payload={"status": "rejected"},
                        create_if_missing=True,
                        task_id=request.task_id,
                        session_id=result.session_id,
                        correlation_id=correlation_id,
                    )
        return result

    def get_queue_stats(self) -> dict[str, int]:
        return self.queue.snapshot()

    def get_strict_progress(self, session_id: str = "") -> dict[str, Any]:
        sid = (session_id or "").strip()
        tasks = self._session_tasks(sid) if sid else []
        return {
            "session_id": sid,
            "strict_mode": self.strict_mode,
            "session_task_count": len(tasks),
            "researcher_done": self._role_completed(tasks, "researcher"),
            "builder_done": self._role_completed(tasks, "builder"),
            "reviewer_done": self._role_completed(tasks, "reviewer"),
        }

    def _validate_strict_sequence(self, request: ExecutionRequest, member: TeamMember) -> None:
        if not self.strict_mode:
            return
        if (request.delegated_by or "").strip().lower() != "lead":
            return
        session_id = (request.parent_session_id or "").strip()
        if not session_id:
            return
        role = (member.role or "").strip().lower()
        if role not in {"builder", "reviewer"}:
            return
        tasks = self._session_tasks(session_id)
        if role == "builder" and not self._role_completed(tasks, "researcher"):
            raise StrictWorkflowError(
                "TEAM_STRICT_MODE 约束：builder 阶段前必须先完成 researcher 阶段。"
            )
        if role == "reviewer" and not self._role_completed(tasks, "builder"):
            raise StrictWorkflowError(
                "TEAM_STRICT_MODE 约束：reviewer 阶段前必须先完成 builder 阶段。"
            )

    def _session_tasks(self, session_id: str) -> list[dict[str, Any]]:
        sid = (session_id or "").strip()
        if not sid:
            return []
        return [
            task
            for task in self.task_board.list_tasks()
            if str(task.get("session_id", "")).strip() == sid
        ]

    def _role_completed(self, tasks: list[dict[str, Any]], role: str) -> bool:
        normalized_role = (role or "").strip().lower()
        member_ids = {
            member.agent_id
            for member in self.team_definition.members.values()
            if (member.role or "").strip().lower() == normalized_role
        }
        if not member_ids:
            return False
        for task in tasks:
            if task.get("status") != "completed":
                continue
            assignee = str(task.get("assignee", "")).strip()
            owner = str(task.get("owner", "")).strip()
            if assignee in member_ids or owner in member_ids:
                return True
        return False
