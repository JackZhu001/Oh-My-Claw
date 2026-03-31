from codemate_agent.team.protocols import RequestTracker


def test_request_tracker_ingests_delegate_and_artifact_messages():
    tracker = RequestTracker()
    request_id = "req123"

    created = tracker.ingest_message(
        {
            "type": "delegate_request",
            "from": "lead",
            "to": "builder",
            "content": "Implement page",
            "request_id": request_id,
            "task_id": 11,
            "correlation_id": "corr-1",
            "session_id": "sid-1",
        }
    )
    assert created is not None
    assert created.protocol == "delegate"
    assert created.task_id == 11

    accepted = tracker.ingest_message(
        {
            "type": "delegate_accept",
            "from": "builder",
            "content": "accepted",
            "request_id": request_id,
            "task_id": 11,
        }
    )
    assert accepted is not None
    assert accepted.status == "approved"

    artifact = tracker.ingest_message(
        {
            "type": "artifact_submit",
            "from": "builder",
            "content": "submitted",
            "request_id": request_id,
            "task_id": 11,
            "manifest_path": "/tmp/manifest.json",
        }
    )
    assert artifact is not None
    assert artifact.protocol == "artifact"
    assert artifact.status == "completed"


def test_request_tracker_snapshot_includes_extended_counts():
    tracker = RequestTracker()
    tracker.create_request("delegate", sender="lead", target="builder", request_id="r1")
    tracker.update_request("delegate", "r1", "failed", responder="builder")
    snap = tracker.snapshot()
    assert "failed" in snap["counts"]["delegate"]
    assert snap["counts"]["delegate"]["failed"] == 1
