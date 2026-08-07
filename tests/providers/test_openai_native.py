import httpx
import pytest

from harness.providers.language.base import ChatMessage, ChatRequest
from harness.providers.language.openai import OpenAIProvider
from tests.providers.fixtures.openai_compat_server import create_openai_compat_app


@pytest.fixture
async def provider():
    app = create_openai_compat_app()
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://fixture")
    adapter = OpenAIProvider(base_url="http://fixture", http_client=client)
    try:
        yield adapter
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_provider_id_is_openai(provider: OpenAIProvider) -> None:
    assert provider.provider_id == "openai"
    assert provider.display_name == "OpenAI"


@pytest.mark.asyncio
async def test_chat_stream_works(provider: OpenAIProvider) -> None:
    request = ChatRequest(
        model="local-model-a", messages=[ChatMessage(role="user", content="hi openai")]
    )
    chunks = [item async for item in provider.chat_stream(request)]
    assert "hi openai" in "".join(c.delta for c in chunks)
