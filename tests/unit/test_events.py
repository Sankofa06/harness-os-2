import asyncio

import pytest

from harness.events.bus import EventBus
from harness.events.model import Event, EventFilter


@pytest.mark.asyncio
async def test_subscriber_receives_matching_events() -> None:
    bus = EventBus()
    sub = bus.subscribe(EventFilter(event_types=["run.started"]))
    await bus.publish(Event(type="run.started", payload={"a": 1}))
    await bus.publish(Event(type="run.completed", payload={"a": 2}))

    event = await asyncio.wait_for(sub.queue.get(), timeout=1)
    assert event.type == "run.started"
    assert sub.queue.empty()


@pytest.mark.asyncio
async def test_wildcard_filter_matches_prefix() -> None:
    bus = EventBus()
    sub = bus.subscribe(EventFilter(event_types=["inference.*"]))
    await bus.publish(Event(type="inference.first_token"))
    event = await asyncio.wait_for(sub.queue.get(), timeout=1)
    assert event.type == "inference.first_token"


@pytest.mark.asyncio
async def test_session_id_filter() -> None:
    bus = EventBus()
    sub = bus.subscribe(EventFilter(session_ids=["ses_a"]))
    await bus.publish(Event(type="x", context={"session_id": "ses_b"}))
    await bus.publish(Event(type="x", context={"session_id": "ses_a"}))
    event = await asyncio.wait_for(sub.queue.get(), timeout=1)
    assert event.context["session_id"] == "ses_a"
    assert sub.queue.empty()


@pytest.mark.asyncio
async def test_publish_never_blocks_on_slow_subscriber() -> None:
    bus = EventBus()
    sub = bus.subscribe()
    for i in range(2000):
        await asyncio.wait_for(bus.publish(Event(type="x", payload={"i": i})), timeout=1)
    assert sub.lagged is True


@pytest.mark.asyncio
async def test_persist_tap_assigns_seq() -> None:
    seen = []

    async def persist(event: Event) -> Event:
        return event.model_copy(update={"seq": len(seen) + 1})

    bus = EventBus(persist=persist)
    result = await bus.publish(Event(type="x"))
    seen.append(result)
    assert result.seq == 1
