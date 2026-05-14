## Why

Agents and automation workflows need a reliable MCP service that can fetch rendered web pages, execute page-side JavaScript, and return readable content through standard MCP transports. Building this service around the Obscura CDP server provides a browser-backed fetch path that can handle JavaScript-rendered pages better than plain HTTP clients.

## What Changes

- Add a Python 3.13 MCP service named for web fetch operations.
- Support both SSE and streamable HTTP MCP transports.
- Connect to a configurable Obscura CDP server using `playwright-core`/Playwright over CDP.
- Add a `fetch` tool that opens one URL, optionally runs JavaScript, and returns a sliced content string.
- Add a `batch-fetch` tool that fetches multiple URLs with the same slicing and optional JavaScript behavior.
- Add a `search` tool that queries mainstream search engines including Baidu, Google, and Bing, returning tabular result data containing titles and URLs.
- Add service configuration for the CDP endpoint and runtime defaults.
- Add Dockerfile support for building and running the service image.

## Capabilities

### New Capabilities

- `web-fetch-mcp-service`: Defines the MCP service transports, configuration, CDP-backed page access, content extraction, batch fetching, search behavior, and Docker packaging.

### Modified Capabilities

None.

## Impact

- Adds a new Python service implementation, dependency management, configuration files, and Docker build assets.
- Introduces runtime dependency on an external Obscura CDP server endpoint.
- Introduces Playwright CDP client usage for browser page navigation and JavaScript evaluation.
- Exposes MCP tool APIs for `fetch`, `batch-fetch`, and `search` over SSE and streamable HTTP transports.
