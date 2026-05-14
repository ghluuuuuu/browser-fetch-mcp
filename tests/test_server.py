import httpx

from browser_fetch_mcp.config import Settings
from browser_fetch_mcp.server import create_app, create_mcp


def test_create_mcp_configures_both_transport_paths() -> None:
    mcp = create_mcp(Settings())

    assert mcp.settings.streamable_http_path == "/mcp"
    assert mcp.settings.sse_path == "/sse"
    assert mcp.settings.message_path == "/messages/"


def test_create_app_exposes_streamable_http_and_sse_routes() -> None:
    app = create_app(Settings())

    paths = {route.path for route in app.routes}

    assert "/mcp" in paths
    assert "/sse" in paths
    assert "/messages" in paths


def test_transport_config_does_not_disable_endpoint_routes() -> None:
    app = create_app(Settings(transport="sse"))

    paths = {route.path for route in app.routes}

    assert "/mcp" in paths
    assert "/sse" in paths


async def test_access_key_rejects_missing_or_invalid_requests() -> None:
    app = create_app(Settings(access_key="secret"))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        missing = await client.get("/sse")
        invalid = await client.get("/sse", headers={"Authorization": "Bearer wrong"})

    assert missing.status_code == 401
    assert missing.json() == {"error": "Unauthorized"}
    assert invalid.status_code == 401


async def test_access_key_accepts_bearer_and_api_key_headers() -> None:
    app = create_app(Settings(access_key="secret"))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        bearer = await client.get("/not-found", headers={"Authorization": "Bearer secret"})
        api_key = await client.get("/not-found", headers={"X-API-Key": "secret"})
        query_key = await client.get("/not-found?api_key=secret")

    assert bearer.status_code != 401
    assert api_key.status_code != 401
    assert query_key.status_code != 401


async def test_fetch_tools_expose_asset_include_flags() -> None:
    mcp = create_mcp(Settings())

    tools = {tool.name: tool for tool in await mcp.list_tools()}

    fetch_schema = tools["fetch"].inputSchema
    batch_schema = tools["batch-fetch"].inputSchema
    assert fetch_schema["properties"]["include_links"]["default"] is False
    assert fetch_schema["properties"]["include_images"]["default"] is False
    assert batch_schema["properties"]["include_links"]["default"] is False
    assert batch_schema["properties"]["include_images"]["default"] is False


async def test_tool_parameter_prompts_are_in_parameter_schema() -> None:
    mcp = create_mcp(Settings())

    tools = {tool.name: tool for tool in await mcp.list_tools()}

    for tool in tools.values():
        for schema in tool.inputSchema["properties"].values():
            assert schema.get("description")
        assert "Args:" not in (tool.description or "")
        assert "Returns:" not in (tool.description or "")

    assert "Absolute http or https URL" in tools["fetch"].inputSchema["properties"]["url"]["description"]
    assert "Search engine" in tools["search"].inputSchema["properties"]["engine"]["description"]
    assert "Image search engine" in tools["search_img"].inputSchema["properties"]["engine"]["description"]
    assert "Markdown image previews" in tools["search_img"].description
    assert "thumbnail or cached image URLs" in tools["search_img"].description
    assert "call `fetch` on the corresponding" in tools["search_img"].description
