import httpx
import pytest

from harness.core.capabilities import AdapterLevel
from harness.providers.language.base import ChatMessage, ChatRequest
from harness.providers.language.lmstudio import LMStudioProvider
from tests.providers.fixtures.lmstudio_server import create_lmstudio_app


@pytest.fixture
async def provider():
    app = create_lmstudio_app()
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://fixture")
    adapter = LMStudioProvider(base_url="http://fixture", http_client=client)
    try:
        yield adapter
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_declares_l5_capabilities(provider: LMStudioProvider) -> None:
    caps = provider.capabilities()
    assert AdapterLevel.L3_LIFECYCLE in caps
    assert AdapterLevel.L5_NATIVE_EXTRAS in caps


@pytest.mark.asyncio
async def test_list_models_reports_rich_native_metadata(provider: LMStudioProvider) -> None:
    models = await provider.list_models()
    by_id = {m.id: m for m in models}

    loaded = by_id["llama-3.1-8b-instruct"]
    assert loaded.loaded is True
    assert loaded.context_length == 131072
    assert loaded.metadata["quantization"] == "Q4_K_M"

    not_loaded = by_id["qwen2.5-7b-instruct"]
    assert not_loaded.loaded is False


@pytest.mark.asyncio
async def test_load_and_unload_model(provider: LMStudioProvider) -> None:
    instance = await provider.load_model("qwen2.5-7b-instruct", flash_attention=True)
    assert instance.instance_id == "qwen2.5-7b-instruct:1"
    assert instance.status == "loaded"
    assert instance.load_time_seconds == 1.23

    await provider.unload_model(instance.instance_id)  # must not raise


@pytest.mark.asyncio
async def test_chat_stream_uses_openai_compatible_endpoint(provider: LMStudioProvider) -> None:
    request = ChatRequest(
        model="llama-3.1-8b-instruct",
        messages=[ChatMessage(role="user", content="hi lmstudio")],
    )
    chunks = [item async for item in provider.chat_stream(request)]
    text = "".join(c.delta for c in chunks)
    assert "hi lmstudio" in text
    assert any(c.finish_reason == "stop" for c in chunks)


@pytest.mark.asyncio
async def test_settings_schema_only_documents_real_load_fields(
    provider: LMStudioProvider,
) -> None:
    schema = provider.settings_schema()
    properties = schema.provider["lmstudio"]["properties"]
    assert set(properties) == {
        "context_length",
        "eval_batch_size",
        "flash_attention",
        "offload_kv_to_gpu",
    }
