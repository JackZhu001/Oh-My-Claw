"""
Default team member definitions.
"""

from __future__ import annotations

from codemate_agent.team.definitions import TeamDefinition, TeamMember


def get_default_team_definition(team_name: str = "default") -> TeamDefinition:
    members = {
        "lead": TeamMember(
            agent_id="lead",
            role="lead",
            display_name="Team Lead",
            system_prompt=(
                "You are the lead coordinator. Break down work, validate outputs, "
                "and keep handoffs concise."
            ),
            allowed_tools=(
                "list_dir",
                "search_files",
                "search_code",
                "read_file",
                "todo_write",
                "task_list",
                "task_get",
                "team_status",
            ),
            denied_tools=("run_shell", "write_file", "append_file", "delete_file"),
            max_turns=12,
        ),
        "researcher": TeamMember(
            agent_id="researcher",
            role="researcher",
            display_name="Researcher",
            system_prompt=(
                "You are a research specialist. Focus on reading, searching, and "
                "producing factual summaries."
            ),
            allowed_tools=(
                "list_dir",
                "search_files",
                "search_code",
                "read_file",
                "memory_read",
                "todo_write",
            ),
            denied_tools=(
                "run_shell",
                "write_file",
                "append_file",
                "delete_file",
                "edit_file",
            ),
            model_policy="light",
            max_turns=12,
        ),
        "builder": TeamMember(
            agent_id="builder",
            role="builder",
            display_name="Builder",
            system_prompt=(
                "You are an implementation specialist. Produce concrete code and "
                "keep edits scoped to the task. You must write real files via tools, "
                "chunk large content (<=1800 chars per chunk), and after 2 write failures "
                "switch to skeleton + append strategy instead of retrying the same call."
            ),
            allowed_tools=(
                "list_dir",
                "search_files",
                "search_code",
                "read_file",
                "skill",
                "write_file",
                "append_file",
                "write_file_chunks",
                "append_file_chunks",
                "edit_file",
                "run_shell",
                "todo_write",
            ),
            max_turns=18,
        ),
        "reviewer": TeamMember(
            agent_id="reviewer",
            role="reviewer",
            display_name="Reviewer",
            system_prompt=(
                "You are a reviewer. Prioritize correctness, regressions, and "
                "missing validation."
            ),
            allowed_tools=(
                "list_dir",
                "search_files",
                "search_code",
                "read_file",
                "skill",
                "run_shell",
                "todo_write",
            ),
            denied_tools=("write_file", "append_file", "delete_file"),
            model_policy="light",
            max_turns=14,
        ),
    }
    return TeamDefinition(team_name=(team_name or "default").strip() or "default", members=members)
