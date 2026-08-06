import pytest
from httpx import ASGITransport, AsyncClient

from harness.api.app import create_app
from harness.core.app import create_application
from harness.core.config import HarnessConfig


@pytest.fixture
async def client():
    config = HarnessConfig()
    config.ui.demo_mode = True  # forces an in-memory DB, no filesystem, no real token
    application = await create_application(config)
    app = create_app(application=application)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac
    await application.close()
