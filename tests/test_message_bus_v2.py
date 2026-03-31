from codemate_agent.team.message_bus import MessageBus


def test_message_bus_send_adds_message_id_and_to(tmp_path):
    bus = MessageBus(tmp_path / "inbox")
    payload = bus.send("lead", "alice", "hello", msg_type="message")
    assert payload["to"] == "alice"
    assert payload["message_id"]


def test_message_bus_ack_and_replay(tmp_path):
    bus = MessageBus(tmp_path / "inbox")
    msg1 = bus.send("lead", "alice", "first")
    msg2 = bus.send("lead", "alice", "second")
    _ = bus.ack_messages("alice", [msg1["message_id"]])

    unread = bus.read_inbox("alice", drain=False, unread_only=True)
    assert len(unread) == 1
    assert unread[0]["message_id"] == msg2["message_id"]

    replay = bus.replay_inbox("alice", limit=1, include_acked=True)
    assert len(replay) == 1
