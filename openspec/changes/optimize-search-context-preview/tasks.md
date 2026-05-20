## 1. Search Result Model and Extraction

- [x] 1.1 Add `snippet` and context status metadata to search result row models with safe defaults for existing callers.
- [x] 1.2 Extend search-engine extraction JavaScript and parsing so Baidu, Google, and Bing rows can include visible SERP snippets when available.
- [x] 1.3 Add or update unit tests for snippet parsing, invalid rows, duplicate rows, and rows without snippets.

## 2. Context Mode Controls

- [x] 2.1 Add validated `context_mode`, `context_top_k`, and `context_max_length` inputs to the search service and MCP tool schema.
- [x] 2.2 Make default search behavior use snippet-only discovery without calling `batch_fetch` for target-page context.
- [x] 2.3 Preserve compatibility for `enable_show_link_context` by mapping explicit legacy usage onto the new context mode behavior.
- [x] 2.4 Implement `preview` mode so only the first `context_top_k` rows receive fetched context sliced to `context_max_length`.
- [x] 2.5 Implement `full` mode so every returned row receives fetched context sliced to `context_max_length`.

## 3. Failure Handling and Metadata

- [x] 3.1 Mark rows whose target-page context was not requested with a not-requested context status.
- [x] 3.2 Mark rows with fetched context status when preview or full enrichment succeeds.
- [x] 3.3 Mark preview rows beyond `context_top_k` with skipped context status.
- [x] 3.4 Preserve search results when an individual preview fetch fails and mark the affected row with error or timeout context status.

## 4. Documentation and Tests

- [x] 4.1 Update MCP tool descriptions to explain `snippet`, `context`, context modes, top-K preview limits, and when to use `fetch` or `batch-fetch`.
- [x] 4.2 Update README usage guidance so default `search` is described as fast discovery and target-page context is opt-in.
- [x] 4.3 Add service-level tests proving default search does not call `batch_fetch`, preview mode fetches only top-K rows, and full mode fetches all rows.
- [x] 4.4 Add schema tests for the new search parameters and returned row fields.
- [ ] 4.5 Run the targeted test suite for search, server schema, and model behavior.
