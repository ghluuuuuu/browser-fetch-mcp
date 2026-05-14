## Context

`BrowserClient.fetch()` currently waits for `domcontentloaded`, then immediately evaluates the default text extractor and page asset extractor. Many modern pages render the initial document shell first and fill visible text, links, or images later through client-side JavaScript, intersection observers, or delayed API responses. In those cases the current flow can return an empty string even though useful content appears moments later.

`batch_fetch()` delegates each URL to `fetch()`, so the same early extraction behavior affects every batch entry.

## Goals / Non-Goals

**Goals:**

- Avoid premature empty results for pages that populate rendered content shortly after navigation.
- Apply the same waiting behavior to `fetch` and every URL processed by `batch-fetch`.
- Keep the MCP tool request parameters and response schemas unchanged.
- Bound all waits by existing navigation timeout settings so calls cannot hang indefinitely.
- Keep failures explicit when the page never produces content.

**Non-Goals:**

- Guarantee extraction from pages that require authentication, user interaction, CAPTCHA solving, or infinite scrolling.
- Add a public wait parameter to the MCP tool schemas in this change.
- Replace the existing content extraction model or introduce a full browser automation workflow.

## Decisions

### Add an internal rendered-content readiness wait

After navigation reaches `domcontentloaded`, run a bounded wait loop before extraction. The loop should repeatedly evaluate a lightweight readiness probe that measures rendered text length and asset counts from the current DOM. It should proceed when useful content is present and stable across consecutive samples, or when the remaining timeout budget is exhausted.

Alternative considered: switch `page.goto(..., wait_until="networkidle")`. This is too brittle for pages with long polling, analytics beacons, or continuously active network activity, and it can add latency without guaranteeing visible content.

### Probe the same data shape used by extraction

The readiness check should look at `document.body.innerText` / `document.documentElement.innerText` and basic link/image counts, matching the signals later returned by `DEFAULT_TEXT_JS` and `PAGE_ASSETS_JS`. This keeps readiness tied to actual output instead of unrelated lifecycle events.

Alternative considered: wait for a generic selector such as `body`. The body exists on almost every page before meaningful lazy-loaded content appears, so it does not solve the early empty result.

### Use conservative bounded polling defaults

Use short polling intervals and require stability for consecutive samples once non-empty content is observed. The wait should be capped by the configured navigation timeout and should leave enough budget for final extraction. Internal constants are acceptable for this change because the public API should stay stable.

Alternative considered: expose user-configurable wait parameters. That may be useful later, but it adds tool schema surface before there is enough evidence about which knobs users need.

### Preserve custom JavaScript behavior

When `exec_js` is provided, still run the readiness wait before evaluation. The requested expression may depend on data populated after initial navigation, and waiting improves consistency without changing the expression contract.

Alternative considered: only wait for default text extraction. That would leave `exec_js` callers exposed to the same timing issue.

## Risks / Trade-offs

- Some pages intentionally render little or no text -> The wait will add bounded latency before returning empty content.
- Pages that update continuously may never look stable -> Proceed after the timeout budget rather than waiting forever.
- Content behind user gestures or scroll-triggered loading may still be missing -> This change improves post-load lazy rendering, not interactive browsing.
- More waiting can reduce throughput for batch fetches -> Keep waits bounded and preserve existing batch concurrency controls.

## Migration Plan

1. Add a reusable browser-page readiness helper.
2. Call it after `page.goto(..., wait_until="domcontentloaded")` and before evaluating requested content.
3. Add unit tests with fake page objects that simulate delayed body text and asset availability.
4. Run the existing test suite to ensure response schemas and batch ordering remain unchanged.

## Open Questions

- Should a later change expose optional tuning for content wait timeout or stability thresholds if users encounter special sites?
