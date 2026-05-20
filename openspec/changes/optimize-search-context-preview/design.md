## Context

`search` currently has two behaviors coupled together: it opens a search-engine result page to discover candidate URLs, then `enable_show_link_context=True` causes every returned URL to be opened through `batch-fetch` before the tool returns. Each target-page preview uses the browser-backed fetch path, including navigation and rendered-content waiting, so the default search latency scales with the number and speed of returned pages.

The existing project documentation and base specification describe `search` as a discovery tool that returns tabular search rows, while `fetch` and `batch-fetch` are the evidence-grade tools for reading source pages. This change restores that separation while preserving an explicit path for callers that want richer one-call previews.

## Goals / Non-Goals

**Goals:**

- Make default `search` calls fast by avoiding target-page navigations unless explicitly requested.
- Extract and return SERP-level `snippet` text when available so callers can rank candidates without fetching target pages.
- Add explicit context preview modes with bounded top-K and maximum-length controls.
- Preserve a compatibility path for the current all-result fetched-context behavior.
- Keep `fetch` and `batch-fetch` as the canonical tools for source-page content used as final evidence.

**Non-Goals:**

- Add a persistent cache in this change.
- Replace browser-backed search with paid or credentialed search APIs.
- Add summarization or LLM ranking to search results.
- Reuse browser cookies or state across unrelated callers.

## Decisions

### Separate SERP snippets from target-page context

Search rows will expose a `snippet` field populated from the search-engine result page when the engine markup provides one. The existing `context` field remains reserved for content fetched from the target URL.

Alternative considered: put SERP snippets into `context`. That would be simpler but misleading, because clients would not know whether the text came from the search engine or from the source page.

### Replace the boolean default with explicit context modes

The `search` tool will accept a `context_mode` option with these semantics:

- `none`: return only title and URL metadata.
- `snippet`: return title, URL, and SERP snippet without opening target pages.
- `preview`: return snippets for all rows and fetched target-page context for at most `context_top_k` rows.
- `full`: fetch target-page context for every returned row, matching the current eager behavior.

The default mode will be `snippet` so the common path opens only the search-engine result page. `enable_show_link_context` can remain as a deprecated compatibility alias during implementation, mapping true to `full` and false to `snippet` unless `context_mode` is explicitly provided.

Alternative considered: only change `enable_show_link_context` to default false. That improves latency but keeps a vague boolean API and does not distinguish SERP snippets from fetched preview context.

### Bound preview work with top-K and max-length controls

`preview` mode will fetch target pages only for the first `context_top_k` parsed rows and will slice each preview to `context_max_length`. Defaults should be conservative, such as top 3 results and roughly 1000 characters per preview. `full` mode can use the same length control and a top-K value that covers all returned rows.

Alternative considered: keep the existing hardcoded 4000-character preview for all modes. That preserves current output size but gives callers no latency or context-budget control.

### Keep preview fetching on the existing batch-fetch path

Preview enrichment will continue to use `BrowserClient.batch_fetch` so it inherits bounded concurrency, input-order result preservation, and partial per-URL error handling. This avoids introducing a second navigation pipeline in the first optimization pass.

Alternative considered: create a separate fast-preview fetch path with shorter rendered-content waits. That could be a future optimization, but the first change should reduce the number and size of page fetches before changing fetch lifecycle semantics.

### Surface context provenance through status metadata

Rows that do or do not receive fetched context should make that state machine explicit. A lightweight `context_status` field can distinguish `not_requested`, `fetched`, `skipped`, `timeout`, `error`, or similar outcomes. This helps clients avoid treating missing context as equivalent to an empty page.

Alternative considered: infer status from whether `context` is empty. That fails for legitimate empty pages and makes timeout/error cases indistinguishable.

## Risks / Trade-offs

- SERP markup differs across engines and changes over time -> Keep snippet extraction inside engine adapters and add fixture/unit coverage for each supported engine where practical.
- Some callers may expect default fetched context -> Preserve an explicit compatibility path and document the new default clearly in tool descriptions and README.
- SERP snippets are not authoritative source content -> Tool descriptions must say snippets are for candidate selection and final answers should use `fetch` or explicit preview/full context.
- Top-K preview can miss relevant lower-ranked pages -> Callers can increase `context_top_k`, choose `full`, or use `batch-fetch` after inspecting snippets.
- Adding multiple options can make the tool harder to understand -> Use mode names that describe depth and keep defaults conservative.
