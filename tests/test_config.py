from pathlib import Path

import pytest
from pydantic import ValidationError

from obscura_web_fetch_mcp.config import load_settings


def test_load_settings_uses_file_and_env_override(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        "cdp_endpoint: ws://file:9222\ntransport: sse\nport: 9000\n",
        encoding="utf-8",
    )

    settings = load_settings(config, env={"CDP_ENDPOINT": "ws://env:9222", "MCP_PORT": "8001"})

    assert settings.cdp_endpoint == "ws://env:9222"
    assert settings.transport == "sse"
    assert settings.port == 8001


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
