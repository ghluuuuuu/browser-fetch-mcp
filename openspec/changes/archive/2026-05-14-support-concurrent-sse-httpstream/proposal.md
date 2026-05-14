## Why

The MCP service currently treats SSE and streamable HTTP as mutually exclusive runtime modes selected by configuration. Clients that support different MCP transports should be able to connect to the same running service without requiring separate processes or a restart.

## What Changes

- Change service startup so one running service exposes both SSE and streamable HTTP transports at the same time.
- Keep the same MCP tools available through both transports.
- Stop using runtime configuration to restrict the service to only one of the two supported HTTP transports.
- Preserve host, port, CDP endpoint, timeout, concurrency, search, and result-limit configuration behavior.
- No breaking change is intended for existing clients that connect through either SSE or streamable HTTP, provided their endpoint paths remain available.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `web-fetch-mcp-service`: Service transport requirements change from configurable single-transport startup to concurrent SSE and streamable HTTP availability.

## Impact

- Service startup and transport registration code.
- Runtime configuration schema and documentation for transport mode behavior.
- Tests or smoke checks that currently assume a single selected transport.
- Docker/runtime usage examples that describe transport selection.
