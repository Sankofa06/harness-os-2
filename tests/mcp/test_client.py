import pytest

from harness.core.errors import ProviderError
from harness.mcp.client import McpClient
from tests.mcp.fixtures import start_fake_mcp_server, stop_fake_mcp_server


@pytest.fixture
async def running_server():
    server, task, info = await start_fake_mcp_server()
    try:
        yield info
    finally:
        await stop_fake_mcp_server(server, task)


@pytest.mark.asyncio
async def test_initialize_returns_server_info(running_server) -> None:
    client = McpClient(running_server.base_url)
    try:
        result = await client.initialize()
        assert result["serverInfo"]["name"] == "fixture-mcp-server"
        assert result["protocolVersion"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_list_tools_returns_real_tool_definitions(running_server) -> None:
    client = McpClient(running_server.base_url)
    try:
        tools = await client.list_tools()
        names = {t["name"] for t in tools}
        assert names == {"search_docs", "create_ticket"}
        search = next(t for t in tools if t["name"] == "search_docs")
        assert search["inputSchema"]["required"] == ["query"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_auth_token_sent_as_bearer_header(running_server) -> None:
    client = McpClient(running_server.base_url, auth_token="s3cr3t-token")
    try:
        result = await client.initialize()
        assert result["receivedAuthorization"] == "Bearer s3cr3t-token"
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_no_auth_header_sent_when_token_unset(running_server) -> None:
    client = McpClient(running_server.base_url)
    try:
        result = await client.initialize()
        assert result["receivedAuthorization"] is None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_unreachable_server_raises_provider_error() -> None:
    client = McpClient("http://127.0.0.1:1/mcp")  # nothing listens on port 1
    try:
        with pytest.raises(ProviderError):
            await client.initialize()
    finally:
        await client.aclose()
