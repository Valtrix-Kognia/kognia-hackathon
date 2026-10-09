import json

from app.voice.event_publisher import EventPublisher


async def test_events_are_sent_in_order_with_session_and_seq() -> None:
    sent: list[str] = []

    async def send(text: str) -> None:
        sent.append(text)

    publisher = EventPublisher("room-a", send)
    publisher.publish("session.started", {"x": 1})
    publisher.publish("agent.listening", {"state": "listening"})
    publisher.start()
    await publisher.aclose()
    events = [json.loads(s) for s in sent]
    assert [e["seq"] for e in events] == [1, 2]
    assert {e["session_id"] for e in events} == {"room-a"}
    assert events[1]["type"] == "agent.listening"


async def test_send_failures_do_not_stop_the_publisher() -> None:
    sent: list[str] = []

    async def flaky(text: str) -> None:
        if not sent and "first" in text:
            sent.append("failed")
            raise RuntimeError("network")
        sent.append(text)

    publisher = EventPublisher("room-b", flaky)
    publisher.start()
    publisher.publish("error.occurred", {"m": "first"})
    publisher.publish("error.occurred", {"m": "second"})
    await publisher.aclose()
    assert any("second" in s for s in sent)


async def test_sessions_are_isolated() -> None:
    a_sent: list[str] = []
    b_sent: list[str] = []

    async def send_a(text: str) -> None:
        a_sent.append(text)

    async def send_b(text: str) -> None:
        b_sent.append(text)

    a, b = EventPublisher("A", send_a), EventPublisher("B", send_b)
    a.start()
    b.start()
    a.publish("agent.thinking", {})
    b.publish("agent.speaking", {})
    await a.aclose()
    await b.aclose()
    assert [json.loads(s)["session_id"] for s in a_sent] == ["A"]
    assert [json.loads(s)["session_id"] for s in b_sent] == ["B"]
