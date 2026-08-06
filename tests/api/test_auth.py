import pytest
from httpx import ASGITransport, AsyncClient

from harness.api.app import create_app
from harness.core.app import create_application
from harness.core.config import HarnessConfig


@pytest.mark.asyncio
async def test_remote_request_without_token_is_rejected() -> None:
    config = HarnessConfig()
    config.ui.demo_mode = True
    application = await create_application(config)
    app = create_app(application=application)
    async with app.router.lifespan_context(app):
        # A non-loopback client address exercises the "remote client, no token" path
        # (DECISIONS.md D-005); the default ASGITransport client is loopback, so it
        # must be overridden explicitly here.
        transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/contacts")
            assert resp.status_code == 401
            assert resp.json()["code"] == "auth_required"
    await application.close()


@pytest.mark.asyncio
async def test_remote_request_with_valid_token_is_accepted() -> None:
    config = HarnessConfig()
    config.ui.demo_mode = True
    application = await create_application(config)
    app = create_app(application=application)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
        headers = {"Authorization": f"Bearer {application.api_token}"}
        async with AsyncClient(
            transport=transport, base_url="http://testserver", headers=headers
        ) as ac:
            resp = await ac.get("/api/v1/contacts")
            assert resp.status_code == 200
    await application.close()


@pytest.mark.asyncio
async def test_remote_request_with_wrong_token_is_rejected() -> None:
    config = HarnessConfig()
    config.ui.demo_mode = True
    application = await create_application(config)
    app = create_app(application=application)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, client=("203.0.113.5", 12345))
        headers = {"Authorization": "Bearer wrong-token"}
        async with AsyncClient(
            transport=transport, base_url="http://testserver", headers=headers
        ) as ac:
            resp = await ac.get("/api/v1/contacts")
            assert resp.status_code == 401
    await application.close()


@pytest.mark.asyncio
async def test_loopback_request_without_token_is_accepted_by_default(client) -> None:
    resp = await client.get("/api/v1/contacts")
    assert resp.status_code == 200
