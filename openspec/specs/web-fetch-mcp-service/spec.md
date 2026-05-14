# web-fetch-mcp-service Specification

## Purpose
TBD - created by archiving change add-web-fetch-mcp-service. Update Purpose after archive.
## Requirements
### Requirement: Service MUST expose MCP transports
The system SHALL provide a Python 3.13 MCP server that exposes SSE mode and streamable HTTP mode concurrently from the same running service process. Both transports SHALL expose the same MCP tools.

#### Scenario: Run with streamable HTTP
- **WHEN** the service starts
- **THEN** it SHALL expose MCP tools over the streamable HTTP endpoint

#### Scenario: Run with SSE
- **WHEN** the service starts
- **THEN** it SHALL expose the same MCP tools over the SSE endpoint

#### Scenario: Run both transports concurrently
- **WHEN** the service is running
- **THEN** clients SHALL be able to connect through the streamable HTTP endpoint and the SSE endpoint without restarting the service or changing configuration

### Requirement: Service MUST load runtime configuration
The system SHALL load runtime configuration for the Obscura CDP endpoint, MCP host, MCP port, navigation timeout, batch concurrency, default search engine, and default result limits from configuration files and environment variables. Environment variables SHALL override file defaults. Transport selection configuration SHALL NOT disable either SSE or streamable HTTP endpoints.

#### Scenario: Environment overrides config file
- **WHEN** a CDP endpoint is defined in both the configuration file and the `CDP_ENDPOINT` environment variable
- **THEN** the service SHALL use the `CDP_ENDPOINT` environment variable value

#### Scenario: Transport configuration does not restrict endpoints
- **WHEN** a transport value is present in configuration or environment variables
- **THEN** the service SHALL still expose both the streamable HTTP endpoint and the SSE endpoint

### Requirement: Fetch tool MUST retrieve rendered page content
The system SHALL provide a `fetch` MCP tool that accepts `url`, `start_index`, `max_length`, and optional `exec_js`. The tool SHALL open the URL through the configured Obscura CDP server, wait for navigation, evaluate JavaScript when requested, and return sliced content beginning at `start_index` with at most `max_length` characters.

#### Scenario: Fetch default text content
- **WHEN** a caller invokes `fetch` with a URL and no `exec_js`
- **THEN** the service SHALL return text extracted from the rendered document body

#### Scenario: Fetch with JavaScript execution
- **WHEN** a caller invokes `fetch` with `exec_js` set to `document.title`
- **THEN** the service SHALL evaluate that JavaScript expression after navigation and return the evaluated result as content

#### Scenario: Fetch applies slicing
- **WHEN** the extracted content is longer than `max_length`
- **THEN** the returned `content` SHALL start at `start_index` and contain no more than `max_length` characters

### Requirement: Batch fetch tool MUST process multiple URLs
The system SHALL provide a `batch-fetch` MCP tool that accepts `urls`, `start_index`, `max_length`, and optional `exec_js`. The tool SHALL fetch all URLs through Obscura CDP with bounded concurrency and return one result per input URL in input order.

#### Scenario: Batch fetch preserves order
- **WHEN** a caller invokes `batch-fetch` with three URLs
- **THEN** the response SHALL contain three result entries in the same order as the input URLs

#### Scenario: Batch fetch reports partial failure
- **WHEN** one URL in a batch fails to navigate but other URLs succeed
- **THEN** the failed URL entry SHALL include error information and the successful URL entries SHALL include their content

### Requirement: Search tool MUST return tabular search results
The system SHALL provide a `search` MCP tool that accepts a keyword and supports mainstream search engines including Baidu, Google, and Bing. The tool SHALL return tabular result data containing each result title and URL.

#### Scenario: Search with default engine
- **WHEN** a caller invokes `search` with only a keyword
- **THEN** the service SHALL use the configured default search engine and return result rows containing `title` and `url`

#### Scenario: Search with selected engine
- **WHEN** a caller invokes `search` with engine set to `bing`
- **THEN** the service SHALL query Bing and return result rows containing `title` and `url`

#### Scenario: Search rejects unsupported engine
- **WHEN** a caller invokes `search` with an unsupported engine name
- **THEN** the service SHALL return a validation error before navigating any page

### Requirement: CDP client MUST use Obscura through Playwright
The system SHALL use Playwright's CDP connection support to connect to the configured Obscura CDP server and perform page navigation, JavaScript evaluation, and content extraction.

#### Scenario: CDP endpoint unavailable
- **WHEN** the configured CDP endpoint is unreachable
- **THEN** tool responses SHALL return a clear connection error without crashing the MCP server process

### Requirement: Docker image MUST run the service
The system SHALL include a Dockerfile that builds a Python 3.13 image for the MCP service and starts the server with configurable runtime environment variables.

#### Scenario: Run container with CDP endpoint
- **WHEN** the Docker image is run with a valid `CDP_ENDPOINT` environment variable
- **THEN** the container SHALL start the MCP service and connect tool calls to that endpoint
