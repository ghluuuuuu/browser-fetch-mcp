# Browser Fetch MCP

Python 3.13 MCP service that fetches rendered pages through a browser CDP endpoint.

## Tools

- `fetch`: open one URL, optionally evaluate `exec_js`, and return sliced content.
- `batch-fetch`: open multiple URLs with bounded concurrency and per-URL results.
- `search`: query `baidu`, `google`, or `bing` and return rows with `title` and `url`.

## Run

```powershell
python -m pip install -e .[dev]
$env:CDP_ENDPOINT = "ws://127.0.0.1:9222"
browser-fetch-mcp
```

The service exposes streamable HTTP at `/mcp` and SSE at `/sse` from the same running process.

## Configuration

Defaults are loaded from `config.example.yaml`. Environment variables override file values:

- `CDP_ENDPOINT`
- `MCP_HOST`
- `MCP_PORT`
- `MCP_ACCESS_KEY`
- `BROWSER_PROXY_SERVER`
- `BROWSER_PROXY_USERNAME`
- `BROWSER_PROXY_PASSWORD`
- `NAVIGATION_TIMEOUT_MS`
- `BATCH_CONCURRENCY`
- `DEFAULT_SEARCH_ENGINE`
- `DEFAULT_SEARCH_LIMIT`
- `MAX_CONTENT_LENGTH`

`MCP_TRANSPORT` is accepted for compatibility with older deployments, but it no longer disables either transport endpoint.

Set `access_key` in the config file or `MCP_ACCESS_KEY` in the environment to require authentication on `/mcp`, `/sse`, and `/messages/`.
Clients can pass the key with `Authorization: Bearer <key>`, `X-API-Key: <key>`, or `?api_key=<key>`.

Set `browser_proxy_server` or `BROWSER_PROXY_SERVER` to route browser page traffic through a proxy.
For SOCKS5, use a value such as `socks5://127.0.0.1:1080`; optional username and password can be set with `browser_proxy_username` / `browser_proxy_password` or the matching environment variables.

## Docker

```powershell
docker build -t browser-fetch-mcp .
docker run --rm -p 8000:8000 -e CDP_ENDPOINT=ws://host.docker.internal:9222 browser-fetch-mcp
```

The image does not bundle a browser. Run Chrome, Chromium, or another compatible CDP server separately and pass its endpoint with `CDP_ENDPOINT`.

## Docker Compose

Use the published GHCR images for deployment:

```powershell
docker compose up -d
```

Use the development compose file to build images locally:

```powershell
docker compose -f docker-compose.dev.yaml up -d --build
```

The deployment compose file uses these images by default:

- `ghcr.io/ghluuuuuu/browser-fetch-mcp:latest`
- `ghcr.io/ghluuuuuu/browser-fetch-mcp-chromote:latest`

Set `BROWSER_FETCH_MCP_IMAGE` or `CHROMOTE_IMAGE` to deploy a specific image tag.
