import httpx
import pytest

from harness.core.capabilities import AdapterLevel
from harness.providers.language.base import ChatMessage, ChatRequest
from harness.providers.language.ollama import OllamaProvider
from tests.providers.fixtures.ollama_server import create_ollama_app, last_keep_alive


@pytest.fixture
async def provider():
    app = create_ollama_app()
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://fixture")
    adapter = OllamaProvider(base_url="http://fixture", http_client=client)
    try:
        yield adapter
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_declares_l4_l5_capabilities(provider: OllamaProvider) -> None:
    caps = provider.capabilities()
    assert AdapterLevel.L4_TELEMETRY in caps
    assert AdapterLevel.L5_NATIVE_EXTRAS in caps


@pytest.mark.asyncio
async def test_list_models(provider: OllamaProvider) -> None:
    models = await provider.list_models()
    assert models[0].id == "llama3.2:latest"
    assert models[0].metadata["family"] == "llama"


@pytest.mark.asyncio
async def test_chat_stream_yields_deltas_then_usage(provider: OllamaProvider) -> None:
    request = ChatRequest(
        model="llama3.2:latest",
        messages=[ChatMessage(role="user", content="hi ollama")],
    )
    chunks = [item async for item in provider.chat_stream(request)]
    text = "".join(c.delta for c in chunks)
    assert "hi ollama" in text
    final = chunks[-1]
    assert final.done is True
    assert final.usage is not None
    assert final.usage.output_tokens == len(chunks) - 1  # one usage-bearing final chunk


@pytest.mark.asyncio
async def test_load_model_sends_empty_prompt_generate(provider: OllamaProvider) -> None:
    instance = await provider.load_model("llama3.2:latest")
    assert instance.instance_id == "llama3.2:latest"
    assert instance.status == "loaded"


@pytest.mark.asyncio
async def test_unload_model_sets_keep_alive_zero(provider: OllamaProvider) -> None:
    await provider.unload_model("llama3.2:latest")
    assert last_keep_alive["llama3.2:latest"] == 0


@pytest.mark.asyncio
async def test_common_settings_translate_to_ollama_options() -> None:
    from harness.providers.language.ollama import _translate_common

    options = _translate_common({"temperature": 0.3, "max_output_tokens": 512})
    assert options == {"temperature": 0.3, "num_predict": 512}
