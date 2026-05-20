## MODIFIED Requirements

### Requirement: Search tool MUST return tabular search results
The system SHALL provide a `search` MCP tool that accepts a keyword and supports mainstream search engines including Baidu, Google, and Bing. The tool SHALL return tabular result data containing each result title and URL. Search rows SHALL include a SERP `snippet` field when the selected search engine exposes visible summary text for the result. Search rows SHALL keep fetched target-page preview content separate from SERP snippets by placing fetched target-page text in `context`.

The `search` tool SHALL support explicit context preview modes. In `none` mode, the tool SHALL return result metadata without SERP snippets or target-page context. In `snippet` mode, the tool SHALL return SERP snippets when available and SHALL NOT open target result URLs for context. In `preview` mode, the tool SHALL return SERP snippets and SHALL fetch target-page context for no more than `context_top_k` returned rows, slicing each fetched preview to at most `context_max_length` characters. In `full` mode, the tool SHALL fetch target-page context for every returned row, slicing each fetched preview to at most `context_max_length` characters.

The default `search` behavior SHALL be optimized for discovery by using snippet-only behavior unless the caller explicitly requests target-page context. The tool SHALL expose context status metadata that lets callers distinguish not-requested context, top-K skipped context, successfully fetched context, and failed preview attempts.

#### Scenario: Search with default engine
- **WHEN** a caller invokes `search` with only a keyword
- **THEN** the service SHALL use the configured default search engine and return result rows containing `title`, `url`, `snippet`, empty target-page `context`, and context status indicating target-page context was not requested

#### Scenario: Search with selected engine
- **WHEN** a caller invokes `search` with engine set to `bing`
- **THEN** the service SHALL query Bing and return result rows containing `title`, `url`, and any extractable SERP `snippet`

#### Scenario: Search rejects unsupported engine
- **WHEN** a caller invokes `search` with an unsupported engine name
- **THEN** the service SHALL return a validation error before navigating any page

#### Scenario: Search preview fetches bounded target-page context
- **WHEN** a caller invokes `search` with context mode set to `preview`, `context_top_k` set to 3, and `context_max_length` set to 1000
- **THEN** the service SHALL fetch target-page context for at most the first 3 returned rows, each fetched row's `context` SHALL contain no more than 1000 characters, and any remaining rows SHALL be marked with context status indicating preview context was skipped by the top-K limit

#### Scenario: Search full context preserves explicit eager enrichment
- **WHEN** a caller invokes `search` with context mode set to `full`
- **THEN** the service SHALL fetch target-page context for every returned row and mark fetched rows with context status indicating fetched target-page context

#### Scenario: Search preview tolerates individual target-page failures
- **WHEN** a caller invokes `search` with context mode set to `preview` and one selected target page fails to fetch
- **THEN** the service SHALL still return the search results and SHALL mark the failed row's context status as an error or timeout without failing the entire search response
