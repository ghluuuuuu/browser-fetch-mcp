## MODIFIED Requirements

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
