from obscura_web_fetch_mcp.config import Settings
from obscura_web_fetch_mcp.server import create_app, create_mcp


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
