import httpx
import pytest

from harness.providers.language.base import ChatMessage, ChatRequest
from harness.providers.language.openrouter import OpenRouterProvider
from tests.providers.fixtures.openrouter_server import FAKE_MODELS, create_openrouter_app


@pytest.fixture
async def provider():
    app = create_openrouter_app()
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://fixture")
    adapter = OpenRouterProvider(base_url="http://fixture", http_client=client)
    try:
        yield adapter
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_list_models_reports_pricing_and_context_length(
    provider: OpenRouterProvider,
) -> None:
    models = await provider.list_models()
    model = models[0]
    assert model.id == FAKE_MODELS[0]["id"]
    assert model.context_length == 200000
    assert model.metadata["pricing_prompt_usd_per_token"] == "0.000003"


@pytest.mark.asyncio
async def test_chat_stream_reports_authoritative_cost(provider: OpenRouterProvider) -> None:
    request = ChatRequest(
        model="anthropic/claude-fixture",
        messages=[ChatMessage(role="user", content="hi openrouter")],
    )
    chunks = [item async for item in provider.chat_stream(request)]
    text = "".join(c.delta for c in chunks)
    assert "hi openrouter" in text

    usage_items = [c for c in chunks if c.usage is not None]
    assert usage_items
    assert usage_items[-1].usage.cost == pytest.approx(0.000123)
