## Context

The project needs a new Python 3.13 MCP service that exposes browser-backed web access tools. The service will not launch or bundle a local browser; it will connect to an already-running Obscura CDP server, which exposes Chrome DevTools Protocol compatibility for Playwright clients.

The service must support two HTTP-facing MCP modes: legacy SSE for clients that still require it, and streamable HTTP for current MCP deployments. Both transports should expose the same tool set and business logic.

## Goals / Non-Goals

**Goals:**

- Provide a Python 3.13 service with MCP tools `fetch`, `batch-fetch`, and `search`.
- Connect to Obscura via a configurable CDP endpoint such as `ws://127.0.0.1:9222`.
- Use Playwright's CDP connection to create browser contexts, open pages, navigate URLs, evaluate JavaScript, and read rendered page content.
- Return deterministic, bounded content using `start_index` and `max_length`.
- Provide configuration files for CDP endpoint, timeout, concurrency, search defaults, host, port, and transport mode.
- Provide Dockerfile packaging for the MCP service image.

**Non-Goals:**

- Implement or vendor the Obscura CDP server itself.
- Provide proxy management, authentication bypass, CAPTCHA solving, or login automation beyond caller-provided JavaScript execution.
- Persist cookies or browser state across tool calls unless explicitly added by a future change.
- Guarantee access to websites that block automation or require interactive challenge solving.

## Decisions

### Use the official Python MCP SDK and FastMCP

The service will use the `mcp` Python package and define tools with `FastMCP`. This gives direct support for Python tool schemas and current MCP transports.

Alternative considered: implementing JSON-RPC, SSE, and streamable HTTP directly with Starlette. That would provide more transport control but add protocol maintenance risk with no clear benefit for this service.

### Use Python Playwright over CDP

Python does not use the JavaScript package name `playwright-core`; the equivalent implementation will depend on the Python `playwright` package while connecting over CDP instead of launching a bundled browser. The service will call `chromium.connect_over_cdp(config.cdp_endpoint)`, create a fresh context/page per fetch operation, and close context/page resources after each call.

Alternative considered: using raw WebSocket CDP messages. That would reduce dependency size but would require hand-written navigation, lifecycle, runtime evaluation, DOM extraction, and error handling.

### Keep browser state isolated per fetch

Each `fetch` request will create an isolated browser context. `batch-fetch` will process URLs with a bounded async concurrency limit and one isolated context per URL.

Alternative considered: reusing one browser context for all calls. That is faster, but creates cookie, storage, and navigation side effects between unrelated MCP callers.

### Extract content through JavaScript evaluation

When `exec_js` is provided, the service will evaluate it on the loaded page and return the serialized result. When `exec_js` is empty, the service will evaluate a default expression that reads visible text from `document.body.innerText`, falling back to `document.documentElement.innerText` or an empty string.

Alternative considered: using Playwright locators and DOM APIs outside page JavaScript. The requested behavior explicitly asks for JavaScript execution, and page-side evaluation keeps custom extraction flexible.

### Return structured tool results

`fetch` will return an object containing `url`, `content`, `start_index`, `max_length`, `content_length`, and optional execution/navigation metadata. `batch-fetch` will return a list of per-URL result objects and preserve input order. Failed entries will include error information without failing the entire batch unless the whole request is invalid.

Alternative considered: returning raw strings only. Structured results make partial failures and slicing metadata testable and easier for MCP clients to consume.

### Implement search with configurable engine adapters

The `search` tool will accept `keyword`, optional `engine`, and optional result limit parameters. It will build engine-specific search URLs for Baidu, Google, and Bing, navigate via Obscura, and evaluate JavaScript selectors to extract titles and URLs into a tabular list.

Alternative considered: using official search APIs. That would be more stable where available but requires credentials and does not match the requested browser/CDP-based fetch behavior.

### Runtime configuration

Configuration will load from a checked-in example file and environment variables. Environment variables take precedence so Docker deployments can inject `CDP_ENDPOINT`, `MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT`, navigation timeout, and batch concurrency without editing the image.

Alternative considered: command-line flags only. Files plus environment variables are easier to use in containers and MCP launch configurations.

## Risks / Trade-offs

- Search result pages change markup frequently -> Keep engine extraction selectors isolated in adapter functions and include tests with mocked/evaluated fixture HTML where practical.
- Obscura CDP compatibility may differ from full Chrome -> Use only common Playwright operations: connect over CDP, new context, new page, goto, evaluate, close.
- `exec_js` can run arbitrary page-side code -> Document that this is intentional tool behavior, execute it only inside the remote page context, and do not expose server-side Python execution.
- Long or hanging pages can block tool calls -> Enforce navigation timeout and per-request maximum content length.
- High batch concurrency can overload Obscura -> Add a configurable concurrency limit with conservative defaults.
- SSE is legacy compared with streamable HTTP -> Keep both transports selectable while documenting streamable HTTP as the default deployment mode.
