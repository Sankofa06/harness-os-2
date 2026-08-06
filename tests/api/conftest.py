import pytest
from httpx import ASGITransport, AsyncClient

from harness.api.app import create_app
from harness.core.app import create_application
from harness.core.config import HarnessConfig


@pytest.fixture
async def harness_app():
    config = HarnessConfig()
    config.ui.demo_mode = True  # forces an in-memory DB, no filesystem, no real token
    application = await create_application(config)
    try:
        yield application
    finally:
        await application.close()


@pytest.fixture
async def client(harness_app):
    app = create_app(application=harness_app)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
