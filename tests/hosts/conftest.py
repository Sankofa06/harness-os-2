import pytest

from tests.hosts.fixtures import RunningSSHServer, start_test_ssh_server


@pytest.fixture
async def ssh_server() -> RunningSSHServer:
    server, info = await start_test_ssh_server()
    try:
        yield info
    finally:
        server.close()
        await server.wait_closed()
