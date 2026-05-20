## Why

The `search` tool currently fetches preview context by opening every result URL by default, so a single search can turn into many browser navigations before returning. This makes search slow and blurs the intended boundary between lightweight result discovery and evidence-grade page fetching.

## What Changes

- Add explicit search context modes so callers can choose fast discovery, SERP snippets, bounded top-result previews, or the existing full-context behavior.
- Return SERP-level snippets separately from target-page context so agents can quickly rank candidates without treating search-engine summaries as fetched source content.
- Limit context preview work with caller-visible controls for top-K enrichment and preview character length.
- Preserve an explicit compatibility path for callers that still need fetched context for every returned result.
- Update tool descriptions and tests so default `search` behavior is fast, predictable, and aligned with `fetch`/`batch-fetch` as the canonical source-reading tools.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `web-fetch-mcp-service`: Search result behavior changes to support SERP snippets and explicit, bounded target-page context preview modes.

## Impact

- Affected code: `src/browser_fetch_mcp/search.py`, `src/browser_fetch_mcp/server.py`, `src/browser_fetch_mcp/models.py`, related search tests, and documentation.
- API impact: `search` gains explicit context preview controls and returns snippet metadata; the current eager all-result context fetch becomes opt-in rather than the default.
- Runtime impact: default search calls should open only the search-engine result page, while preview/full modes continue to use browser-backed target-page fetches under bounded settings.
