from pathlib import Path

import pytest
from pydantic import ValidationError

from browser_fetch_mcp.config import load_settings


def test_load_settings_uses_file_and_env_override(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        (
            "cdp_endpoint: ws://file:9222\n"
            "transport: sse\n"
            "port: 9000\n"
            "access_key: file-key\n"
            "browser_proxy_server: socks5://file-proxy:1080\n"
        ),
        encoding="utf-8",
    )

    settings = load_settings(
        config,
        env={
            "CDP_ENDPOINT": "ws://env:9222",
            "MCP_PORT": "8001",
            "MCP_ACCESS_KEY": " env-key ",
            "BROWSER_PROXY_SERVER": " socks5://env-proxy:1080 ",
            "BROWSER_PROXY_USERNAME": " proxy-user ",
            "BROWSER_PROXY_PASSWORD": " proxy-pass ",
        },
    )

    assert settings.cdp_endpoint == "ws://env:9222"
    assert settings.transport == "sse"
    assert settings.port == 8001
    assert settings.access_key == "env-key"
    assert settings.browser_proxy_server == "socks5://env-proxy:1080"
    assert settings.browser_proxy_username == "proxy-user"
    assert settings.browser_proxy_password == "proxy-pass"


def test_load_settings_accepts_legacy_transport_env(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("cdp_endpoint: ws://file:9222\n", encoding="utf-8")

    settings = load_settings(config, env={"MCP_TRANSPORT": "sse"})

    assert settings.transport == "sse"


def test_invalid_cdp_endpoint_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("cdp_endpoint: ftp://example\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="cdp_endpoint"):
        load_settings(config, env={})


def test_invalid_browser_proxy_server_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("browser_proxy_server: ftp://127.0.0.1:1080\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="browser_proxy_server"):
        load_settings(config, env={})


def test_browser_proxy_server_accepts_common_sock_alias(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("browser_proxy_server: sock5://127.0.0.1:1080\n", encoding="utf-8")

    settings = load_settings(config, env={})

    assert settings.browser_proxy_server == "socks5://127.0.0.1:1080"
