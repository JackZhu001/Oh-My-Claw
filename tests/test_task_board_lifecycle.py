from codemate_agent.team.task_board import TaskBoard


def test_task_board_claim_sets_lease_and_attempt(tmp_path):
    board = TaskBoard(tmp_path / ".tasks")
    task = board.create_task("build feature", max_attempts=3)
    claimed = board.claim_task(task["id"], "builder", lease_ttl_sec=120)
    assert claimed is not None
    assert claimed["status"] == "in_progress"
    assert claimed["attempt"] == 1
    assert claimed["lease_owner"] == "builder"
    assert claimed["lease_expires_at"] > 0


def test_task_board_renew_and_release_lease(tmp_path):
    board = TaskBoard(tmp_path / ".tasks")
    task = board.create_task("write docs")
    _ = board.claim_task(task["id"], "alice", lease_ttl_sec=90)

    renewed = board.renew_lease(task["id"], "alice", lease_ttl_sec=180)
    assert renewed is not None
    assert renewed["lease_expires_at"] > 0

    released = board.release_lease(task["id"], "alice", to_status="pending")
    assert released is not None
    assert released["status"] == "pending"
    assert released["owner"] == ""
    assert released["lease_owner"] == ""


def test_task_board_mark_failed_with_retry_and_terminal(tmp_path):
    board = TaskBoard(tmp_path / ".tasks")
    task = board.create_task("retry task", max_attempts=2)
    _ = board.claim_task(task["id"], "builder")
    first = board.mark_failed(task["id"], owner="builder", reason="net err", retryable=True)
    assert first is not None
    assert first["status"] == "pending"
    assert first["failure_reason"] == "net err"

    _ = board.claim_task(task["id"], "builder")
    second = board.mark_failed(task["id"], owner="builder", reason="perm err", retryable=True)
    assert second is not None
    assert second["status"] == "failed"
    assert second["failure_reason"] == "perm err"
