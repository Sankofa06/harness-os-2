"""ANA-001's acceptance bar (SPEC/DEFINITION_OF_DONE.md Analytics bullets
1-2): every inference run persists tokens/duration/model/contact/binding,
and tok/s + TTFT are stored when calculable. Also covers the DoD's
"outcome status" requirement for runs that fail or get canceled, not just
ones that succeed.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from harness.agents.runloop import handle_user_message, run_contact
from harness.core.app import create_application
from harness.core.capabilities import AdapterLevel
from harness.core.config import HarnessConfig
from harness.core.domain import Binding, Contact
from harness.core.ids import new_id
from harness.providers.language.base import (
    ChatRequest,
    ChatStreamItem,
    ChatUsage,
    LanguageProvider,
)


class TimedProvider(LanguageProvider):
    """Streams two deltas with a real delay between them so TTFT and
    duration are genuinely measurable, not just non-crashing zeros.
    """

    provider_id = "timed-fixture"
    display_name = "Timed Fixture"

    def capabilities(self) -> frozenset[AdapterLevel]:
        return frozenset({AdapterLevel.L0_CHAT, AdapterLevel.L4_TELEMETRY})

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        await asyncio.sleep(0.05)
        yield ChatStreamItem(delta="hello ")
        await asyncio.sleep(0.05)
        yield ChatStreamItem(delta="world")
        yield ChatStreamItem(
            done=True,
            finish_reason="stop",
            usage=ChatUsage(input_tokens=5, output_tokens=2),
        )


class FailingProvider(LanguageProvider):
    provider_id = "failing-fixture"
    display_name = "Failing Fixture"

    def capabilities(self) -> frozenset[AdapterLevel]:
        return frozenset({AdapterLevel.L0_CHAT})

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        raise RuntimeError("provider exploded")
        yield  # pragma: no cover -- makes this an async generator


@pytest.fixture
async def app():
    config = HarnessConfig()
    config.ui.demo_mode = True
    application = await create_application(config)
    try:
        yield application
    finally:
        await application.close()


async def _one_contact_session(app, provider: LanguageProvider, handle: str):
    app.providers.register(provider)
    contact = await app.contacts.create(
        Contact(
            id=new_id("con"),
            handle=handle,
            display_name=handle,
            binding=Binding(provider=provider.provider_id, model="fixture-model-v1"),
        )
    )
    session = await app.sessions.create("s", [contact.id])
    return contact, session


@pytest.mark.asyncio
async def test_successful_run_persists_tokens_duration_ttft_and_tokens_per_second(app) -> None:
    contact, session = await _one_contact_session(app, TimedProvider(), "timed")

    outcomes = await handle_user_message(app, session.id, "@timed hi")
    assert outcomes[0].status == "succeeded"
    run_id = outcomes[0].run_id

    metrics = await app.runs.get_metrics(run_id)
    assert metrics is not None
    assert metrics.input_tokens == 5
    assert metrics.output_tokens == 2
    assert metrics.outcome == "succeeded"
    assert metrics.finish_reason == "stop"
    # Real delays (0.05s before first token, another 0.05s before the
    # second), so these must be genuinely positive, not just non-None.
    assert metrics.duration_ms is not None and metrics.duration_ms >= 90
    assert metrics.ttft_ms is not None and metrics.ttft_ms >= 40
    assert metrics.tokens_per_second is not None and metrics.tokens_per_second > 0

    # "persists ... model/contact/binding": the Run links to a Contact and
    # a binding_snapshot carrying the resolved model/provider/hosts.
    run = await app.runs.get(run_id)
    assert run.contact_id == contact.id
    assert run.binding_snapshot_id is not None
    snapshot = await app.runs.get_snapshot(run.binding_snapshot_id)
    assert snapshot.model == "fixture-model-v1"
    assert snapshot.provider == "timed-fixture"
    assert snapshot.inference_host == "local"
    assert snapshot.execution_host == "local"


@pytest.mark.asyncio
async def test_failed_run_still_persists_an_outcome_and_duration(app) -> None:
    _contact, session = await _one_contact_session(app, FailingProvider(), "failer")

    outcomes = await handle_user_message(app, session.id, "@failer hi")
    assert outcomes[0].status == "failed"
    run_id = outcomes[0].run_id

    metrics = await app.runs.get_metrics(run_id)
    assert metrics is not None
    assert metrics.outcome == "failed"
    assert metrics.duration_ms is not None and metrics.duration_ms >= 0
    assert metrics.input_tokens is None  # never reached the provider's usage reporting


class SlowStartProvider(LanguageProvider):
    """A long delay before the first token, so the run's setup work --
    several sequential DB round-trips resolving bindings/history/tool
    schemas/skills, all of which happen before this provider is even
    called -- has comfortable room to finish before cancellation lands
    inside this provider's own wait, rather than racing one of those
    earlier DB calls (SQLite's single pooled connection is not safe to
    have invalidated mid-operation by an external cancel()).
    """

    provider_id = "slow-start-fixture"
    display_name = "Slow Start Fixture"

    def capabilities(self) -> frozenset[AdapterLevel]:
        return frozenset({AdapterLevel.L0_CHAT})

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        await asyncio.sleep(2.0)
        yield ChatStreamItem(delta="too slow", done=True, finish_reason="stop")  # pragma: no cover


@pytest.mark.asyncio
async def test_canceled_run_persists_canceled_outcome(app) -> None:
    contact, session = await _one_contact_session(app, SlowStartProvider(), "cancelme")
    run_id = new_id("run")

    task = asyncio.create_task(run_contact(app, session.id, contact, new_id("run"), run_id))
    await asyncio.sleep(0.3)  # well past setup's DB round-trips, into the provider's own wait
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    metrics = await app.runs.get_metrics(run_id)
    assert metrics is not None
    assert metrics.outcome == "canceled"
