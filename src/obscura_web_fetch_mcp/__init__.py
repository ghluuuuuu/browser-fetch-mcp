"""Obscura-backed web fetch MCP service."""

from .config import Settings, load_settings
from .server import create_app, create_mcp

__all__ = ["Settings", "create_app", "create_mcp", "load_settings"]
