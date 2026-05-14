## Why

Some JavaScript-rendered pages populate their visible text and asset lists after the initial `domcontentloaded` event. `fetch` and `batch-fetch` can currently return empty or incomplete content when lazy-loaded data has not settled yet.

## What Changes

- Add post-navigation waiting behavior before extracting default page text and assets.
- Wait for page content to become non-empty and stable enough to avoid returning premature empty results.
- Apply the same waiting behavior to each URL processed by `batch-fetch`.
- Keep existing request parameters and response schemas unchanged.
- Preserve navigation timeout behavior so slow pages still fail clearly instead of waiting indefinitely.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `web-fetch-mcp-service`: `fetch` and `batch-fetch` shall wait for lazy-loaded rendered content before extracting and returning page data.

## Impact

- CDP page navigation and extraction logic in the browser client.
- Tests for fetch timing, empty content handling, and batch fetch behavior.
- Runtime configuration may need internal defaults for content wait timing, but no public API change is required.
