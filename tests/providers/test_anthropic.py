import httpx
import pytest

from harness.providers.language.anthropic import AnthropicProvider
from harness.providers.language.base import ChatMessage, ChatRequest
from tests.providers.fixtures.anthropic_server import create_anthropic_app


@pytest.fixture
async def provider():
    app = create_anthropic_app()
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://fixture")
    adapter = AnthropicProvider(base_url="http://fixture", http_client=client)
    try:
        yield adapter
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_chat_stream_translates_system_message_and_events(
    provider: AnthropicProvider,
) -> None:
    request = ChatRequest(
        model="claude-fixture",
        messages=[
            ChatMessage(role="system", content="Be terse."),
            ChatMessage(role="user", content="hi anthropic"),
        ],
    )
    chunks = [item async for item in provider.chat_stream(request)]
    text = "".join(c.delta for c in chunks)
    assert "hi anthropic" in text

    final = chunks[-1]
    assert final.done is True
    assert final.finish_reason == "end_turn"
    assert final.usage is not None
    assert final.usage.input_tokens == 11
    assert final.usage.output_tokens is not None


@pytest.mark.asyncio
async def test_max_tokens_defaults_when_not_specified(provider: AnthropicProvider) -> None:
    # Anthropic requires max_tokens; the adapter must supply a default rather than
    # send a request the API would reject.
    request = ChatRequest(model="claude-fixture", messages=[ChatMessage(role="user", content="x")])
    chunks = [item async for item in provider.chat_stream(request)]
    assert chunks  # did not raise / fixture accepted the request
