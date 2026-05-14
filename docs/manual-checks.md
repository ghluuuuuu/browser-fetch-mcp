# Manual Integration Checks

These checks require a running Obscura CDP server.

1. Start Obscura and note its CDP endpoint, for example `ws://127.0.0.1:9222`.
2. Start the MCP service:

   ```powershell
   $env:CDP_ENDPOINT = "ws://127.0.0.1:9222"
   obscura-web-fetch-mcp
   ```

3. Connect an MCP client to `http://127.0.0.1:8000/mcp`.
4. Call `fetch` with `url=https://example.com`.
5. Call `fetch` with `url=https://example.com` and `exec_js=document.title`.
6. Call `batch-fetch` with two simple URLs and confirm the result order matches input order.
7. Call `search` with `keyword=obscura cdp` and `engine=bing`.
8. Without restarting the service, connect an MCP client to `http://127.0.0.1:8000/sse`.
9. Call `fetch` through the SSE client and confirm it returns the same tool behavior.
