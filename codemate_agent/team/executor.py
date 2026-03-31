"""
Team member executor.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from codemate_agent.team.artifacts import ensure_artifact_dir, list_artifacts, write_manifest
from codemate_agent.team.definitions import ExecutionRequest, ExecutionResult, TeamMember, normalize_cwd
from codemate_agent.tools.task.subagent_runner import SubagentRunner

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Execute delegated tasks with isolated per-member sessions."""

    def __init__(
        self,
        *,
        main_llm_client,
        tool_registry,
        workspace_dir: Path,
        light_llm_client=None,
    ) -> None:
        self.main_llm_client = main_llm_client
        self.light_llm_client = light_llm_client or main_llm_client
        self.tool_registry = tool_registry
        self.workspace_dir = Path(workspace_dir).resolve()

    def execute(self, request: ExecutionRequest, member: TeamMember) -> ExecutionResult:
        started_at = time.time()
        session_id = f"{member.agent_id}-{uuid.uuid4().hex[:8]}"

        task_key = request.task_id if request.task_id is not None else request.request_id
        artifact_dir = (
            Path(request.artifact_dir).resolve()
            if request.artifact_dir
            else ensure_artifact_dir(self.workspace_dir, task_key)
        )

        cwd = normalize_cwd(request.cwd, self.workspace_dir)
        prompt = self._build_prompt(request, member)
        llm_client = self._select_llm_client(member)

        try:
            runner = SubagentRunner(
                llm_client=llm_client,
                tool_registry=self.tool_registry,
                subagent_type=self._role_to_subagent_type(member.role),
                max_steps=max(1, int(member.max_turns)),
                workspace_dir=cwd,
                allowed_tools=set(member.allowed_tools) if member.allowed_tools else None,
                denied_tools=set(member.denied_tools) if member.denied_tools else None,
                system_prompt_override=member.system_prompt or None,
            )
            runner_result = runner.run(request.title, prompt)
            finished_at = time.time()
            gate_error = self._validate_completion_gate(
                role=(member.role or "").strip().lower(),
                tool_usage=dict(runner_result.tool_usage),
                runner_success=bool(runner_result.success),
                has_registered_tools=bool(self.tool_registry.get_all()) if self.tool_registry else False,
            )
            status = "completed" if (runner_result.success and not gate_error) else "failed"
            summary = runner_result.content.strip() or "No summary returned."
            if gate_error:
                summary = f"{summary}\n\n{gate_error}".strip()
            manifest = write_manifest(
                artifact_dir,
                task_id=request.task_id if request.task_id is not None else request.request_id,
                agent_id=member.agent_id,
                request_id=request.request_id,
                status=status,
                summary=summary,
                extra={
                    "tool_usage": dict(runner_result.tool_usage),
                    "gate_error": gate_error or "",
                },
            )
            return ExecutionResult(
                request_id=request.request_id,
                task_id=request.task_id,
                agent_id=member.agent_id,
                status=status,
                summary=summary,
                artifact_paths=list_artifacts(artifact_dir),
                artifact_manifest_path=str(manifest),
                session_id=session_id,
                error=runner_result.error or gate_error or "",
                tool_usage=dict(runner_result.tool_usage),
                started_at=started_at,
                finished_at=finished_at,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Delegated execution failed for member=%s", member.agent_id)
            finished_at = time.time()
            summary = f"Execution failed: {exc}"
            manifest = write_manifest(
                artifact_dir,
                task_id=request.task_id if request.task_id is not None else request.request_id,
                agent_id=member.agent_id,
                request_id=request.request_id,
                status="failed",
                summary=summary,
                extra={"error": str(exc)},
            )
            return ExecutionResult(
                request_id=request.request_id,
                task_id=request.task_id,
                agent_id=member.agent_id,
                status="failed",
                summary=summary,
                artifact_paths=list_artifacts(artifact_dir),
                artifact_manifest_path=str(manifest),
                session_id=session_id,
                error=str(exc),
                tool_usage={},
                started_at=started_at,
                finished_at=finished_at,
            )

    def _select_llm_client(self, member: TeamMember):
        if (member.model_policy or "").strip().lower() == "light":
            return self.light_llm_client
        return self.main_llm_client

    def _build_prompt(self, request: ExecutionRequest, member: TeamMember) -> str:
        sections = [request.instructions.strip()]
        if request.context_summary:
            sections.append(f"Context:\n{request.context_summary.strip()}")
        role = (member.role or "").strip().lower()
        if role == "builder":
            sections.append(
                "Builder protocol:\n"
                "- 必须通过真实工具写入文件，禁止只输出代码文本。\n"
                "- 优先使用 write_file_chunks / append_file_chunks。\n"
                "- 每个 content/chunk <= 1800 字符。\n"
                "- 任一写文件工具失败 2 次后，立即降级为“骨架 + 分段追加”，不要重复同一失败调用。\n"
                "- 收尾必须 read_file 校验关键标题/段落是否写入。"
            )
        elif role == "researcher":
            sections.append(
                "Research protocol:\n"
                "- 结论必须基于 read_file/search_* 的结果，不要臆测。\n"
                "- 对比信息给出来源文件路径。"
            )
        elif role == "reviewer":
            sections.append(
                "Review protocol:\n"
                "- 先 read_file 验证产物存在与关键标题完整。\n"
                "- 再对照任务约束列出缺漏或通过结论。"
            )
        sections.append(
            "Output requirements:\n"
            "- Keep the result concise.\n"
            "- If files are produced, write them directly instead of inlining large content."
        )
        return "\n\n".join(section for section in sections if section)

    def _role_to_subagent_type(self, role: str) -> str:
        normalized = (role or "").strip().lower()
        if normalized == "researcher":
            return "explore"
        if normalized == "reviewer":
            return "summary"
        if normalized == "lead":
            return "plan"
        return "general"

    def _validate_completion_gate(
        self,
        *,
        role: str,
        tool_usage: dict[str, int],
        runner_success: bool,
        has_registered_tools: bool,
    ) -> str:
        if not runner_success:
            return ""
        if not has_registered_tools:
            return ""

        if role == "builder":
            write_count = sum(
                int(tool_usage.get(tool, 0))
                for tool in ("write_file", "append_file", "write_file_chunks", "append_file_chunks", "edit_file")
            )
            read_count = int(tool_usage.get("read_file", 0))
            if write_count <= 0:
                return "Builder completion gate failed: missing write-tool evidence."
            if read_count <= 0:
                return "Builder completion gate failed: missing read_file verification evidence."

        if role == "reviewer":
            read_count = int(tool_usage.get("read_file", 0))
            shell_count = int(tool_usage.get("run_shell", 0))
            if read_count + shell_count <= 0:
                return "Reviewer completion gate failed: missing validation evidence (read_file/run_shell)."

        return ""
