## 1. Inspect MCP SDK Transport APIs

- [x] 1.1 Identify the installed `FastMCP` public APIs for building streamable HTTP and SSE ASGI applications.
- [x] 1.2 Confirm whether one `FastMCP` instance can safely mount both transport apps in one ASGI process.

## 2. Service Startup

- [x] 2.1 Replace single-transport startup with startup that serves both `/mcp` and `/sse` from the same host and port.
- [x] 2.2 Keep tool registration centralized through the existing `create_mcp(settings)` path.
- [x] 2.3 Ensure transport configuration values no longer decide which endpoint is enabled.

## 3. Configuration Compatibility

- [x] 3.1 Update settings handling so existing `transport` / `MCP_TRANSPORT` inputs remain accepted during the transition.
- [x] 3.2 Remove transport selection from default examples and runtime documentation.
- [x] 3.3 Update Docker defaults so the image no longer suggests single-transport mode selection.

## 4. Verification

- [x] 4.1 Add or update tests that verify both `/mcp` and `/sse` endpoint paths are available from one service instance.
- [x] 4.2 Add or update tests proving transport configuration does not disable either endpoint.
- [x] 4.3 Run the project test suite.

## 5. Manual Checks and Docs

- [x] 5.1 Update manual check instructions to start one service and connect clients to both `/mcp` and `/sse`.
- [x] 5.2 Update README connection instructions to describe concurrent transport support.
