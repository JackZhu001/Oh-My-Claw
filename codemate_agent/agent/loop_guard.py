"""
LoopGuard

集中管理工具失败纠偏、提前结束防护与循环告警。
"""

from __future__ import annotations

from typing import Optional


class LoopGuard:
    def __init__(
        self,
        max_consecutive_failures: int = 3,
        max_premature_finishes: int = 3,
    ) -> None:
        self._max_consecutive_failures = max(1, int(max_consecutive_failures))
        self._max_premature_finishes = max(1, int(max_premature_finishes))
        self._consecutive_failures: dict[str, int] = {}
        self._premature_finish_attempts = 0
        self._loop_count = 0

    def reset(self) -> None:
        self._consecutive_failures.clear()
        self._premature_finish_attempts = 0
        self._loop_count = 0

    def reset_tool(self, tool_name: str) -> None:
        if tool_name in self._consecutive_failures:
            self._consecutive_failures[tool_name] = 0

    def reset_premature(self) -> None:
        self._premature_finish_attempts = 0

    def on_tool_result(self, tool_name: str, result: str) -> Optional[str]:
        """工具返回后检查。返回干预消息（若需），否则 None。"""
        if self._is_error_result(result):
            count = self._consecutive_failures.get(tool_name, 0) + 1
            self._consecutive_failures[tool_name] = count
        else:
            self._consecutive_failures[tool_name] = 0

        worst_tool = max(self._consecutive_failures, key=self._consecutive_failures.get, default=None)
        worst_count = self._consecutive_failures.get(worst_tool, 0) if worst_tool else 0
        if worst_tool and worst_count >= self._max_consecutive_failures:
            message = (
                f"⚠️ 工具 '{worst_tool}' 连续 {worst_count} 次调用失败。\n\n"
                "这通常意味着当前方法不可行。可能的原因：\n"
                "1. 内容过长，超过单次输出限制\n"
                "2. 参数格式不正确（若参数反复为空，说明 context 过大导致输出被截断，"
                "请先用 run_shell 写入一个较短的文件骨架，再逐段 append）\n"
                "3. 目标文件/路径不存在\n\n"
                "建议：请尝试将任务分解为更小的步骤，或使用不同的方法。\n\n"
                "NEXT_ACTION: 更换策略——如果在写文件，改用 write_file_chunks；"
                "如果在读文件，先用 list_dir 确认路径；如果在执行命令，先用 run_shell 验证文件存在。"
            )
            self._consecutive_failures[worst_tool] = 0
            return message
        return None

    def is_error_result(self, result: str) -> bool:
        return self._is_error_result(result)

    def on_llm_response(
        self,
        content: str,
        has_unfinished_plan: bool,
        is_substantive: bool,
        is_non_final_progress: bool,
    ) -> Optional[str]:
        """LLM 文本响应后检查是否提前结束。"""
        if not has_unfinished_plan:
            return None
        if is_substantive and not is_non_final_progress:
            return None

        if self._premature_finish_attempts >= self._max_premature_finishes:
            return None

        self._premature_finish_attempts += 1
        return (
            "当前计划尚未完成，请继续执行并产出实际结果。"
            "不要只输出思考过程；请调用合适工具完成文件写入或明确给出可交付产物。"
        )

    def on_loop_detected(self) -> dict:
        """返回 loop 处理信息: {count, forced}"""
        self._loop_count += 1
        forced = self._loop_count >= 3
        if forced:
            self._loop_count = 0
        return {"count": self._loop_count if not forced else 3, "forced": forced}

    @staticmethod
    def _is_error_result(result: str) -> bool:
        if result is None:
            return False
        text = str(result).strip()
        if not text:
            return False

        lowered = text.lower()
        prefix_markers = (
            "错误:",
            "失败:",
            "❌",
            "error:",
            "exception:",
            "traceback",
            "工具执行失败:",
            "参数验证失败:",
            "用户取消了操作:",
        )
        if any(lowered.startswith(marker.lower()) for marker in prefix_markers):
            return True

        # task 工具使用结构化文本返回；只有显式 error/failed 才按失败处理。
        if "--- task result ---" in lowered and (
            "状态: error" in lowered
            or "status: error" in lowered
            or "status: failed" in lowered
            or '"status": "error"' in lowered
            or '"status":"error"' in lowered
            or '"status": "failed"' in lowered
            or '"status":"failed"' in lowered
            or "错误 [team_strict_violation]" in lowered
            or "错误 [team_dispatch_error]" in lowered
        ):
            return True

        embedded_markers = (
            "\ntraceback",
            "命令不在允许列表",
            "检测到越界路径访问",
            "nameerror:",
            "typeerror:",
            "valueerror:",
        )
        return any(marker.lower() in lowered for marker in embedded_markers)
