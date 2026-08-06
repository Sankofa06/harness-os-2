"""In-process async event bus with persistence tap and backpressure-safe fanout."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from harness.events.model import Event, EventFilter

logger = logging.getLogger(__name__)

# A slow subscriber's queue is bounded; on overflow we drop its oldest events and mark
# it lagged — the client recovers by replaying from its last cursor (SPEC/API_CONTRACT.md).
_QUEUE_SIZE = 1024

PersistFn = Callable[[Event], Awaitable[Event]]


class Subscription:
    def __init__(self, bus: EventBus, filter_: EventFilter) -> None:
        self._bus = bus
        self.filter = filter_
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_SIZE)
        self.lagged = False

    async def __aiter__(self) -> AsyncIterator[Event]:
        while True:
            yield await self.queue.get()

    def close(self) -> None:
        self._bus.unsubscribe(self)


class EventBus:
    """Publishes events to subscribers after an optional persistence tap assigns ``seq``."""

    def __init__(self, persist: PersistFn | None = None) -> None:
        self._persist = persist
        self._subscribers: set[Subscription] = set()

    def subscribe(self, filter_: EventFilter | None = None) -> Subscription:
        sub = Subscription(self, filter_ or EventFilter())
        self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        self._subscribers.discard(sub)

    async def publish(self, event: Event) -> Event:
        if self._persist is not None:
            event = await self._persist(event)
        for sub in list(self._subscribers):
            if not sub.filter.matches(event):
                continue
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                sub.lagged = True
                try:
                    sub.queue.get_nowait()
                    sub.queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):  # pragma: no cover - race
                    logger.warning("dropped event %s for lagged subscriber", event.event_id)
        return event
