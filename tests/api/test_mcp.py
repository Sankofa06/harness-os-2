import pytest

from tests.mcp.fixtures import FAKE_TOOLS, start_fake_mcp_server, stop_fake_mcp_server


@pytest.fixture
async def running_server():
    server, task, info = await start_fake_mcp_server()
    try:
        yield info
    finally:
        await stop_fake_mcp_server(server, task)


@pytest.mark.asyncio
async def test_create_and_list_mcp_servers(client) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "docs-server", "base_url": "http://127.0.0.1:9/mcp"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["display_name"] == "docs-server"
    assert body["enabled"] is True
    assert body["last_indexed_at"] is None

    listed = await client.get("/api/v1/mcp/servers")
    assert any(s["id"] == body["id"] for s in listed.json())


@pytest.mark.asyncio
async def test_indexing_populates_compact_index_without_schemas(client, running_server) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "docs-server", "base_url": running_server.base_url},
    )
    server_id = created.json()["id"]

    indexed = await client.post(f"/api/v1/mcp/servers/{server_id}/index")
    assert indexed.status_code == 200
    entries = indexed.json()
    assert {e["tool_name"] for e in entries} == {"search_docs", "create_ticket"}
    for entry in entries:
        # The compact index never carries the schema body itself.
        assert "schema" not in entry
        assert "inputSchema" not in entry
        assert entry["server_id"] == server_id
        assert entry["trust_class"] == "network"
        assert entry["estimated_schema_tokens"] > 0

    server_after = await client.get(f"/api/v1/mcp/servers/{server_id}")
    assert server_after.json()["last_indexed_at"] is not None


@pytest.mark.asyncio
async def test_tool_index_endpoint_lists_across_or_within_one_server(
    client, running_server
) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "docs-server", "base_url": running_server.base_url},
    )
    server_id = created.json()["id"]
    await client.post(f"/api/v1/mcp/servers/{server_id}/index")

    all_entries = await client.get("/api/v1/mcp/tools/index")
    assert len(all_entries.json()) == len(FAKE_TOOLS)

    scoped = await client.get("/api/v1/mcp/tools/index", params={"server_id": server_id})
    assert len(scoped.json()) == len(FAKE_TOOLS)

    other = await client.get("/api/v1/mcp/tools/index", params={"server_id": "mcpsrv_nope"})
    assert other.json() == []


@pytest.mark.asyncio
async def test_tool_schema_is_fetched_lazily_by_a_separate_endpoint(client, running_server) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "docs-server", "base_url": running_server.base_url},
    )
    server_id = created.json()["id"]
    indexed = await client.post(f"/api/v1/mcp/servers/{server_id}/index")
    search_entry = next(e for e in indexed.json() if e["tool_name"] == "search_docs")

    schema = await client.get(f"/api/v1/mcp/tools/{search_entry['id']}/schema")
    assert schema.status_code == 200
    assert schema.json()["required"] == ["query"]


@pytest.mark.asyncio
async def test_reindexing_replaces_stale_entries(client, running_server) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "docs-server", "base_url": running_server.base_url},
    )
    server_id = created.json()["id"]

    first = await client.post(f"/api/v1/mcp/servers/{server_id}/index")
    second = await client.post(f"/api/v1/mcp/servers/{server_id}/index")
    assert len(first.json()) == len(second.json()) == len(FAKE_TOOLS)

    # Re-indexing didn't accumulate duplicate rows for the same tools.
    index = await client.get("/api/v1/mcp/tools/index", params={"server_id": server_id})
    assert len(index.json()) == len(FAKE_TOOLS)


@pytest.mark.asyncio
async def test_delete_mcp_server_cascades_its_index(client, running_server) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "docs-server", "base_url": running_server.base_url},
    )
    server_id = created.json()["id"]
    await client.post(f"/api/v1/mcp/servers/{server_id}/index")

    deleted = await client.delete(f"/api/v1/mcp/servers/{server_id}")
    assert deleted.status_code == 204

    index = await client.get("/api/v1/mcp/tools/index", params={"server_id": server_id})
    assert index.json() == []


@pytest.mark.asyncio
async def test_indexing_resolves_secret_ref_to_bearer_token(client) -> None:
    import os

    os.environ["HARNESS_MCP_TEST_TOKEN"] = "s3cr3t-token"
    server, task, info = await start_fake_mcp_server(required_token="s3cr3t-token")
    try:
        secret = await client.post(
            "/api/v1/secrets",
            json={"name": "mcp-server-token", "kind": "env", "target": "HARNESS_MCP_TEST_TOKEN"},
        )
        secret_id = secret.json()["id"]

        created = await client.post(
            "/api/v1/mcp/servers",
            json={
                "display_name": "authed-server",
                "base_url": info.base_url,
                "secret_ref_id": secret_id,
            },
        )
        assert created.json()["secret_ref_id"] == secret_id
        server_id = created.json()["id"]

        # The fixture server rejects every call unless it carries the exact bearer
        # token above — indexing succeeding proves the resolved secret was sent,
        # not merely accepted by the client constructor.
        indexed = await client.post(f"/api/v1/mcp/servers/{server_id}/index")
        assert indexed.status_code == 200
        assert {e["tool_name"] for e in indexed.json()} == {"search_docs", "create_ticket"}
    finally:
        await stop_fake_mcp_server(server, task)
        del os.environ["HARNESS_MCP_TEST_TOKEN"]


@pytest.mark.asyncio
async def test_indexing_without_secret_ref_fails_against_an_authed_server(client) -> None:
    server, task, info = await start_fake_mcp_server(required_token="s3cr3t-token")
    try:
        created = await client.post(
            "/api/v1/mcp/servers",
            json={"display_name": "authed-server", "base_url": info.base_url},
        )
        server_id = created.json()["id"]

        resp = await client.post(f"/api/v1/mcp/servers/{server_id}/index")
        assert resp.status_code == 502
    finally:
        await stop_fake_mcp_server(server, task)


@pytest.mark.asyncio
async def test_indexing_an_unreachable_server_fails_clearly(client) -> None:
    created = await client.post(
        "/api/v1/mcp/servers",
        json={"display_name": "unreachable", "base_url": "http://127.0.0.1:1/mcp"},
    )
    server_id = created.json()["id"]

    resp = await client.post(f"/api/v1/mcp/servers/{server_id}/index")
    assert resp.status_code == 502
