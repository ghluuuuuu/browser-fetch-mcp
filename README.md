# Obscura Web Fetch MCP

Python 3.13 MCP service that fetches rendered pages through an Obscura CDP endpoint.

## Tools

- `fetch`: open one URL, optionally evaluate `exec_js`, and return sliced content.
- `batch-fetch`: open multiple URLs with bounded concurrency and per-URL results.
- `search`: query `baidu`, `google`, or `bing` and return rows with `title` and `url`.

## Run

```powershell
python -m pip install -e .[dev]
$env:CDP_ENDPOINT = "ws://127.0.0.1:9222"
obscura-web-fetch-mcp
```

The service exposes streamable HTTP at `/mcp` and SSE at `/sse` from the same running process.

## Configuration

Defaults are loaded from `config.example.yaml`. Environment variables override file values:

- `CDP_ENDPOINT`
- `MCP_HOST`
- `MCP_PORT`
- `NAVIGATION_TIMEOUT_MS`
- `BATCH_CONCURRENCY`
- `DEFAULT_SEARCH_ENGINE`
- `DEFAULT_SEARCH_LIMIT`
- `MAX_CONTENT_LENGTH`

`MCP_TRANSPORT` is accepted for compatibility with older deployments, but it no longer disables either transport endpoint.

## Docker

```powershell
docker build -t obscura-web-fetch-mcp .
docker run --rm -p 8000:8000 -e CDP_ENDPOINT=ws://host.docker.internal:9222 obscura-web-fetch-mcp
```

The image does not bundle Obscura or a browser. Run Obscura separately and pass its CDP endpoint with `CDP_ENDPOINT`.
