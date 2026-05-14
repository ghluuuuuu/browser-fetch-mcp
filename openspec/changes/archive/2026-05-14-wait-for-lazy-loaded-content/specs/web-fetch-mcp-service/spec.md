## MODIFIED Requirements

### Requirement: Fetch tool MUST retrieve rendered page content
The system SHALL provide a `fetch` MCP tool that accepts `url`, `start_index`, `max_length`, and optional `exec_js`. The tool SHALL open the URL through the configured Obscura CDP server, wait for navigation, wait for rendered page content to become available when it is populated after initial navigation, evaluate JavaScript when requested, and return sliced content beginning at `start_index` with at most `max_length` characters.

#### Scenario: Fetch default text content
- **WHEN** a caller invokes `fetch` with a URL and no `exec_js`
- **THEN** the service SHALL return text extracted from the rendered document body

#### Scenario: Fetch waits for lazy-loaded text content
- **WHEN** a caller invokes `fetch` for a page whose body text is empty at `domcontentloaded` and becomes available shortly afterward
- **THEN** the service SHALL wait for the rendered text before returning the fetched content

#### Scenario: Fetch with JavaScript execution
- **WHEN** a caller invokes `fetch` with `exec_js` set to `document.title`
- **THEN** the service SHALL evaluate that JavaScript expression after navigation and rendered-content readiness waiting and return the evaluated result as content

#### Scenario: Fetch applies slicing
- **WHEN** the extracted content is longer than `max_length`
- **THEN** the returned `content` SHALL start at `start_index` and contain no more than `max_length` characters

#### Scenario: Fetch remains bounded when content never appears
- **WHEN** a caller invokes `fetch` for a page that does not produce rendered text or assets before the configured timeout budget is exhausted
- **THEN** the service SHALL return a bounded result or clear error without waiting indefinitely

### Requirement: Batch fetch tool MUST process multiple URLs
The system SHALL provide a `batch-fetch` MCP tool that accepts `urls`, `start_index`, `max_length`, and optional `exec_js`. The tool SHALL fetch all URLs through Obscura CDP with bounded concurrency, wait for rendered page content for each URL using the same behavior as `fetch`, and return one result per input URL in input order.

#### Scenario: Batch fetch preserves order
- **WHEN** a caller invokes `batch-fetch` with three URLs
- **THEN** the response SHALL contain three result entries in the same order as the input URLs

#### Scenario: Batch fetch waits for lazy-loaded content per URL
- **WHEN** a caller invokes `batch-fetch` with URLs whose rendered content appears after initial navigation
- **THEN** each successful result SHALL reflect content extracted after that URL's rendered-content readiness waiting

#### Scenario: Batch fetch reports partial failure
- **WHEN** one URL in a batch fails to navigate but other URLs succeed
- **THEN** the failed URL entry SHALL include error information and the successful URL entries SHALL include their content
