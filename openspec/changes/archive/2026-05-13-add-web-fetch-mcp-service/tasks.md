## 1. Project Setup

- [x] 1.1 Create the Python service package structure for the MCP server.
- [x] 1.2 Add Python 3.13 dependency management with MCP SDK, Playwright, configuration, and test dependencies.
- [x] 1.3 Add service entry points for running the MCP server from the command line.

## 2. Configuration

- [x] 2.1 Add a checked-in example configuration file for CDP endpoint, transport, host, port, timeouts, concurrency, and search defaults.
- [x] 2.2 Implement configuration loading with environment variable overrides.
- [x] 2.3 Validate required configuration values and return clear startup errors for invalid settings.

## 3. CDP Browser Client

- [x] 3.1 Implement a Playwright CDP client that connects to the configured Obscura endpoint.
- [x] 3.2 Implement page lifecycle handling with isolated browser contexts per fetch.
- [x] 3.3 Add navigation timeout handling and resource cleanup on success and failure.
- [x] 3.4 Implement JavaScript evaluation and default rendered text extraction.

## 4. MCP Tools

- [x] 4.1 Implement the `fetch` tool with URL validation, optional `exec_js`, slicing by `start_index` and `max_length`, and structured response metadata.
- [x] 4.2 Implement the `batch-fetch` tool with bounded concurrency, input-order result preservation, and per-URL partial error reporting.
- [x] 4.3 Implement the `search` tool with Baidu, Google, and Bing adapters returning tabular rows with `title` and `url`.
- [x] 4.4 Add validation for unsupported search engines and invalid pagination or result limit inputs.

## 5. Transports

- [x] 5.1 Wire the MCP app to run in streamable HTTP mode.
- [x] 5.2 Wire the MCP app to run in SSE mode.
- [x] 5.3 Ensure both transports expose the same tool definitions and runtime configuration.

## 6. Packaging

- [x] 6.1 Add Dockerfile using Python 3.13 and service dependency installation.
- [x] 6.2 Add container runtime environment documentation or sample commands for setting the Obscura CDP endpoint and transport.
- [x] 6.3 Add a `.dockerignore` file to keep development artifacts out of the image context.

## 7. Verification

- [x] 7.1 Add unit tests for configuration loading and environment overrides.
- [x] 7.2 Add unit tests for content slicing and result serialization.
- [x] 7.3 Add tests for search result parsing using static HTML fixtures.
- [x] 7.4 Add integration-test hooks or documented manual checks for connecting to a live Obscura CDP server.
- [x] 7.5 Run formatting, linting, and tests before marking implementation complete.
