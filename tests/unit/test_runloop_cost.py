from collections.abc import AsyncIterator

import pytest

from harness.agents.runloop import handle_user_message
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


class CostReportingProvider(LanguageProvider):
    provider_id = "cost-fixture"
    display_name = "Cost Fixture"

    def capabilities(self) -> frozenset[AdapterLevel]:
        return frozenset({AdapterLevel.L0_CHAT, AdapterLevel.L4_TELEMETRY})

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamItem]:
        yield ChatStreamItem(delta="priced reply")
        yield ChatStreamItem(
            done=True,
            finish_reason="stop",
            usage=ChatUsage(input_tokens=10, output_tokens=2, cost=0.00042),
        )


@pytest.mark.asyncio
async def test_run_metrics_capture_authoritative_provider_cost() -> None:
    config = HarnessConfig()
    config.ui.demo_mode = True
    app = await create_application(config)
    app.providers.register(CostReportingProvider())
    try:
        contact = await app.contacts.create(
            Contact(
                id=new_id("con"),
                handle="priced",
                display_name="Priced",
                binding=Binding(provider="cost-fixture", model="whatever"),
            )
        )
        session = await app.sessions.create("s", [contact.id])

        outcomes = await handle_user_message(app, session.id, "@priced hi")
        assert outcomes[0].status == "succeeded"

        metrics = await app.runs.get_metrics(outcomes[0].run_id)
        assert metrics is not None
        assert metrics.cost_estimate == pytest.approx(0.00042)
    finally:
        await app.close()
