from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

Transport = Literal["sse", "streamable-http"]
SearchEngine = Literal["baidu", "google", "bing"]


class Settings(BaseModel):
    cdp_endpoint: str = Field(default="ws://127.0.0.1:9222", min_length=1)
    transport: Transport = "streamable-http"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    access_key: str = ""
    browser_proxy_server: str = ""
    browser_proxy_username: str = ""
    browser_proxy_password: str = ""
    navigation_timeout_ms: int = Field(default=30_000, ge=1)
    batch_concurrency: int = Field(default=3, ge=1, le=32)
    default_search_engine: SearchEngine = "bing"
    default_search_limit: int = Field(default=10, ge=1, le=50)
    max_content_length: int = Field(default=20_000, ge=1, le=1_000_000)

    @field_validator("cdp_endpoint")
    @classmethod
    def validate_cdp_endpoint(cls, value: str) -> str:
        if not value.startswith(("ws://", "wss://", "http://", "https://")):
            raise ValueError("cdp_endpoint must start with ws://, wss://, http://, or https://")
        return value

    @field_validator("access_key")
    @classmethod
    def normalize_access_key(cls, value: str) -> str:
        return value.strip()

    @field_validator("browser_proxy_server")
    @classmethod
    def validate_browser_proxy_server(cls, value: str) -> str:
        value = value.strip()
        if value.startswith("sock5://"):
            value = "socks5://" + value.removeprefix("sock5://")
        if value.startswith("sock4://"):
            value = "socks4://" + value.removeprefix("sock4://")
        if value and not value.startswith(("http://", "https://", "socks4://", "socks5://")):
            raise ValueError("browser_proxy_server must start with http://, https://, socks4://, or socks5://")
        return value

    @field_validator("browser_proxy_username", "browser_proxy_password")
    @classmethod
    def normalize_browser_proxy_credentials(cls, value: str) -> str:
        return value.strip()


ENV_MAP = {
    "CDP_ENDPOINT": "cdp_endpoint",
    "MCP_TRANSPORT": "transport",
    "MCP_HOST": "host",
    "MCP_PORT": "port",
    "MCP_ACCESS_KEY": "access_key",
    "BROWSER_PROXY_SERVER": "browser_proxy_server",
    "BROWSER_PROXY_USERNAME": "browser_proxy_username",
    "BROWSER_PROXY_PASSWORD": "browser_proxy_password",
    "NAVIGATION_TIMEOUT_MS": "navigation_timeout_ms",
    "BATCH_CONCURRENCY": "batch_concurrency",
    "DEFAULT_SEARCH_ENGINE": "default_search_engine",
    "DEFAULT_SEARCH_LIMIT": "default_search_limit",
    "MAX_CONTENT_LENGTH": "max_content_length",
}


def _read_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return loaded


def _env_overrides(env: dict[str, str] | None = None) -> dict[str, str]:
    source = env if env is not None else os.environ
    return {field: source[name] for name, field in ENV_MAP.items() if name in source}


def load_settings(
    config_path: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> Settings:
    path = Path(config_path or os.getenv("WEB_FETCH_MCP_CONFIG", "config.example.yaml"))
    values = _read_config_file(path)
    values.update(_env_overrides(env))
    return Settings.model_validate(values)
