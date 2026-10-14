"""CRE-004: `A1111Client` against a real local fixture A1111-compatible
server (`tests/creative/a1111_fixtures.py`), not mocks — including the
"partial capabilities" condition the acceptance bar calls for explicitly.
"""

from __future__ import annotations

import pytest

from harness.core.errors import ProviderError, UnsupportedCapabilityError
from harness.providers.creative.a1111.client import A1111Client
from tests.creative.a1111_fixtures import start_fake_a1111_server, stop_fake_a1111_server


@pytest.fixture
async def running_server():
    server, task, info = await start_fake_a1111_server()
    try:
        yield info
    finally:
        await stop_fake_a1111_server(server, task)


@pytest.fixture
async def partial_server():
    server, task, info = await start_fake_a1111_server(
        omit_endpoints=frozenset({"loras", "schedulers"})
    )
    try:
        yield info
    finally:
        await stop_fake_a1111_server(server, task)


@pytest.mark.asyncio
async def test_discover_capabilities_on_a_full_server(running_server) -> None:
    client = A1111Client(running_server.base_url)
    try:
        caps = await client.discover_capabilities()
        assert caps == frozenset(
            {
                "txt2img",
                "img2img",
                "options",
                "samplers",
                "schedulers",
                "sd_models",
                "sd_vae",
                "loras",
                "progress",
                "interrupt",
                "extras",
            }
        )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_discover_capabilities_on_a_partial_server_omits_missing_ones(
    partial_server,
) -> None:
    client = A1111Client(partial_server.base_url)
    try:
        caps = await client.discover_capabilities()
        assert "loras" not in caps
        assert "schedulers" not in caps
        # Everything else is still correctly detected present.
        assert {"txt2img", "img2img", "options", "samplers", "progress"} <= caps
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_calling_a_missing_endpoint_raises_unsupported_not_generic_error(
    partial_server,
) -> None:
    client = A1111Client(partial_server.base_url)
    try:
        with pytest.raises(UnsupportedCapabilityError):
            await client.loras()
        with pytest.raises(UnsupportedCapabilityError):
            await client.schedulers()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_txt2img_returns_real_images_and_info(running_server) -> None:
    client = A1111Client(running_server.base_url)
    try:
        result = await client.txt2img(prompt="a cat", steps=20, cfg_scale=7.0)
        assert len(result["images"]) == 1
        assert result["parameters"]["prompt"] == "a cat"
        assert "seed" in result["info"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_img2img_returns_real_images(running_server) -> None:
    client = A1111Client(running_server.base_url)
    try:
        result = await client.img2img(init_images=["ZmFrZQ=="], denoising_strength=0.5)
        assert len(result["images"]) == 2
        assert "init_images" not in result["parameters"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_options_get_and_set(running_server) -> None:
    client = A1111Client(running_server.base_url)
    try:
        options = await client.get_options()
        assert options["sd_model_checkpoint"]
        await client.set_options({"sd_model_checkpoint": "other.safetensors"})
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_samplers_sd_models_sd_vae_loras(running_server) -> None:
    client = A1111Client(running_server.base_url)
    try:
        samplers = await client.samplers()
        assert samplers[0]["name"]
        models = await client.sd_models()
        assert models[0]["title"]
        vaes = await client.sd_vae()
        assert vaes[0]["model_name"]
        loras = await client.loras()
        assert loras[0]["name"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_progress_and_interrupt(running_server) -> None:
    client = A1111Client(running_server.base_url)
    try:
        status = await client.progress()
        assert "progress" in status
        await client.interrupt()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_extra_single_image(running_server) -> None:
    client = A1111Client(running_server.base_url)
    try:
        result = await client.extra_single_image(
            image="ZmFrZQ==", upscaling_resize=2, upscaler_1="None"
        )
        assert result["image"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_unreachable_server_raises_provider_error() -> None:
    client = A1111Client("http://127.0.0.1:1")  # nothing listens on port 1
    try:
        with pytest.raises(ProviderError):
            await client.get_options()
    finally:
        await client.aclose()
