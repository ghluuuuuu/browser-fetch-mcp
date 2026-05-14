## 1. Readiness Probe

- [x] 1.1 Add a lightweight rendered-content probe that reports body/root text length plus link and image counts.
- [x] 1.2 Add a bounded wait helper that polls the probe until content is non-empty and stable or the timeout budget is exhausted.
- [x] 1.3 Ensure the wait helper treats text, links, or images as useful rendered content signals.

## 2. Fetch Integration

- [x] 2.1 Invoke rendered-content waiting after `page.goto(..., wait_until="domcontentloaded")` and before default extraction.
- [x] 2.2 Invoke the same waiting step before evaluating caller-provided `exec_js`.
- [x] 2.3 Keep all waits bounded by existing `navigation_timeout_ms` behavior.

## 3. Batch Fetch Integration

- [x] 3.1 Ensure `batch-fetch` uses the updated single-URL fetch flow for every URL.
- [x] 3.2 Preserve existing batch concurrency, input ordering, and partial failure behavior.

## 4. Tests

- [x] 4.1 Add tests for delayed text becoming available after initial navigation.
- [x] 4.2 Add tests for asset-only pages where links or images appear before body text.
- [x] 4.3 Add tests that the wait exits without hanging when content never appears.
- [x] 4.4 Add or update batch fetch tests to confirm the updated per-URL waiting behavior is used.

## 5. Verification

- [x] 5.1 Run the project test suite.
- [x] 5.2 Review whether README or manual checks need an example note about lazy-loaded page handling.
