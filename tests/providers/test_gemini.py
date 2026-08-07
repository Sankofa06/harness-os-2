import httpx
import pytest

from harness.providers.language.base import ChatMessage, ChatRequest
from harness.providers.language.gemini import GeminiProvider
from tests.providers.fixtures.gemini_server import FAKE_MODELS, create_gemini_app


@pytest.fixture
async def provider():
    app = create_gemini_app()
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://fixture")
    adapter = GeminiProvider(base_url="http://fixture", http_client=client)
    try:
        yield adapter
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_list_models(provider: GeminiProvider) -> None:
    models = await provider.list_models()
    assert models[0].id == "gemini-fixture"
    assert models[0].context_length == FAKE_MODELS[0]["inputTokenLimit"]


@pytest.mark.asyncio
async def test_chat_stream_maps_assistant_role_to_model_and_reports_usage(
    provider: GeminiProvider,
) -> None:
    request = ChatRequest(
        model="gemini-fixture",
        messages=[
            ChatMessage(role="system", content="Be terse."),
            ChatMessage(role="user", content="hi gemini"),
        ],
    )
    chunks = [item async for item in provider.chat_stream(request)]
    text = "".join(c.delta for c in chunks)
    assert "hi gemini" in text

    final = chunks[-1]
    assert final.done is True
    assert final.finish_reason == "STOP"
    assert final.usage is not None
    assert final.usage.output_tokens is not None
