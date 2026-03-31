from codemate_agent.agent.loop_guard import LoopGuard


def test_error_detection_avoids_false_positive_for_error_handling_text():
    guard = LoopGuard()
    result = "# 错误处理\n这里描述的是错误处理策略，不是工具失败。"
    assert guard.is_error_result(result) is False


def test_error_detection_still_flags_real_errors():
    guard = LoopGuard()
    assert guard.is_error_result("错误: 路径不存在") is True
    assert guard.is_error_result("Traceback (most recent call last): ...") is True


def test_error_detection_flags_task_result_error_status():
    guard = LoopGuard()
    task_result = (
        "--- TASK RESULT ---\n"
        "状态: error\n"
        "--- 结果 ---\n"
        "错误 [TEAM_DISPATCH_ERROR]: dispatch lane unavailable"
    )
    assert guard.is_error_result(task_result) is True


def test_error_detection_does_not_flag_task_result_success_status():
    guard = LoopGuard()
    task_result = (
        "--- TASK RESULT ---\n"
        "状态: success\n"
        "--- 结果 ---\n"
        "Delegated execution finished."
    )
    assert guard.is_error_result(task_result) is False
