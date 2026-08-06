import httpx
import pytest

from harness.providers.language.base import ChatMessage, ChatRequest
from harness.providers.language.openai_compat import OpenAICompatibleProvider
from tests.providers.fixtures.openai_compat_server import FAKE_MODELS, create_openai_compat_app


@pytest.fixture
async def provider():
    app = create_openai_compat_app()
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://fixture")
    adapter = OpenAICompatibleProvider(
        provider_id="openai_compat_fixture",
        display_name="Fixture OpenAI-compatible",
        base_url="http://fixture",
        http_client=client,
    )
    try:
        yield adapter
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_list_models(provider: OpenAICompatibleProvider) -> None:
    models = await provider.list_models()
    assert {m.id for m in models} == set(FAKE_MODELS)


@pytest.mark.asyncio
async def test_chat_stream_yields_deltas_then_usage(provider: OpenAICompatibleProvider) -> None:
    request = ChatRequest(
        model="local-model-a",
        messages=[ChatMessage(role="user", content="hello fixture")],
    )
    chunks = [item async for item in provider.chat_stream(request)]

    text = "".join(c.delta for c in chunks)
    assert "hello fixture" in text
    assert any(c.finish_reason == "stop" for c in chunks)

    usage_items = [c for c in chunks if c.usage is not None]
    assert usage_items
    assert usage_items[-1].usage.output_tokens is not None


@pytest.mark.asyncio
async def test_capabilities_declared() -> None:
    provider = OpenAICompatibleProvider("x", "X", "http://fixture")
    from harness.core.capabilities import AdapterLevel

    caps = provider.capabilities()
    assert AdapterLevel.L0_CHAT in caps
    assert AdapterLevel.L1_TOOLS in caps
    await provider.aclose()
