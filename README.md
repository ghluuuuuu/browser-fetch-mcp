# Browser Fetch MCP

Browser Fetch MCP 是一个 MCP 服务，目标是让 AI Agent 更好地浏览网页内容。
它不是简单地发起 HTTP 请求，也不依赖搜索结果摘要，而是通过 CDP 驱动真实的 Chrome/Chromium 浏览器，
像用户一样渲染页面，并返回适合 AI 上下文窗口使用的清晰、可控的页面数据。

这个项目的核心目标很简单：让 AI 模型可以更可靠地发现网页、打开网页、读取网页，并基于真实网页内容进行推理。
当目标页面依赖 JavaScript 渲染、懒加载内容、搜索结果发现、图片元数据，或需要通过代理访问时，它会特别有用。

## 为什么需要这个项目

AI Agent 在浏览网页时经常会遇到几个问题：原始 HTTP 响应不等于浏览器里最终看到的页面，搜索引擎摘要不能作为可靠信息源，
而完整网页内容又可能太大，直接塞进模型上下文会很难处理。Browser Fetch MCP 把浏览器渲染、搜索发现、结构化提取和内容切片封装成一组 MCP 工具，
让 AI 可以用更接近真实浏览器的方式获取网页内容。

使用它，AI Agent 可以：

- 搜索网页，发现候选页面。
- 在真实浏览器中打开搜索结果页面。
- 读取渲染后的页面文本，而不是不完整的原始 HTML。
- 提取链接、图片、图片尺寸，以及可选的 JavaScript 执行结果。
- 批量读取多个页面，同时控制输出大小。
- 基于实际抓取到的网页内容回答问题，而不是基于搜索结果摘要。

## 功能特点

- 通过 Chrome/Chromium CDP 端点进行真实浏览器渲染。
- 提供 `fetch` 和 `batch-fetch`，用于读取网页文本、链接、图片和可选的 JavaScript 执行结果。
- 支持 `baidu`、`google`、`bing` 网页搜索，返回候选 URL，供后续 `fetch` 使用。
- 支持图片搜索，返回图片 URL、来源页面链接和可用的尺寸信息。
- 同一个服务进程同时提供 Streamable HTTP 和 SSE MCP 端点。
- 支持可选访问密钥，便于在线部署时做访问保护。
- 支持浏览器代理，包括 SOCKS5，用于目标页面访问流量。
- 支持并发限制和内容切片，让大页面也能适配 AI 上下文窗口。

## MCP 工具

### `fetch`

在浏览器中打开一个 URL，并返回切片后的页面内容。它也可以按需返回页面链接、图片，以及可选 `exec_js` 表达式的执行结果。

### `batch-fetch`

使用受控并发打开多个 URL，并为每个 URL 返回一个结构化结果。适合 AI Agent 在回答前对多个候选来源进行对比阅读。

### `search`

查询 `baidu`、`google` 或 `bing`，返回标题、摘要、URL 等搜索结果元数据。搜索结果只建议用于发现候选页面；真正作为依据前，请继续使用 `fetch` 打开来源页面。

### `search_img`

搜索互联网图片，并返回图片结果元数据，包括图片 URL、来源页面链接，以及可用的尺寸信息。

## 推荐 AI 使用流程

1. 使用 `search` 发现候选 URL。
2. 使用 `fetch` 或 `batch-fetch` 读取真实来源页面。
3. 只有在需要时才请求链接和图片，避免占用过多上下文。
4. 对页面内特定内容提取，可以使用 `exec_js` 编写浏览器端 JavaScript。
5. 最终回答应基于 `fetch` 得到的页面内容，而不是搜索结果摘要。

## 本地运行

```powershell
python -m pip install -e .[dev]
$env:CDP_ENDPOINT = "ws://127.0.0.1:9222"
browser-fetch-mcp
```

服务启动后会在同一个进程中提供：

- Streamable HTTP: `/mcp`
- SSE: `/sse`

## 配置

默认配置会从 `config.example.yaml` 加载。环境变量会覆盖配置文件中的值：

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

`MCP_TRANSPORT` 会被兼容读取，但它不再用于禁用任何传输端点。

如果需要访问鉴权，可以在配置文件中设置 `access_key`，或通过环境变量 `MCP_ACCESS_KEY` 设置。
开启后，`/mcp`、`/sse` 和 `/messages/` 都会要求认证。客户端可以通过以下任一方式传入密钥：

- `Authorization: Bearer <key>`
- `X-API-Key: <key>`
- `?api_key=<key>`

如果需要让浏览器页面访问流量走代理，可以设置 `browser_proxy_server` 或 `BROWSER_PROXY_SERVER`。
SOCKS5 示例：`socks5://127.0.0.1:1080`。
如代理需要用户名和密码，可以设置 `browser_proxy_username` / `browser_proxy_password`，或对应的环境变量。

## Docker

```powershell
docker build -t browser-fetch-mcp .
docker run --rm -p 8000:8000 -e CDP_ENDPOINT=ws://host.docker.internal:9222 browser-fetch-mcp
```

该镜像不包含浏览器。请单独运行 Chrome、Chromium 或其他兼容 CDP 的浏览器服务，并通过 `CDP_ENDPOINT` 传入它的地址。

## Docker Compose 本地部署

本地部署推荐直接修改 `docker-compose.yaml`，然后用 Docker Compose 启动服务。该 compose 文件会启动两个服务：

- `chromote`：浏览器服务，在 compose 内部网络中提供 CDP 端点。
- `web-fetch-mcp`：MCP 服务，通过 `CDP_ENDPOINT` 连接到 `chromote`。

默认配置已经可以直接用于本地部署：

- MCP HTTP 端点：`http://127.0.0.1:8000/mcp`
- MCP SSE 端点：`http://127.0.0.1:8000/sse`
- Chromote Web UI：`http://127.0.0.1:8080`
- 内部浏览器端点：`http://172.28.10.10:9222`

常见需要在 `docker-compose.yaml` 中修改的配置：

- `MCP_ACCESS_KEY`：如果希望服务要求认证，可以设置访问密钥。
- `BROWSER_PROXY_SERVER`：让浏览器访问目标网页时走代理，例如 `socks5://127.0.0.1:1080`。
- `BROWSER_PROXY_USERNAME` 和 `BROWSER_PROXY_PASSWORD`：代理需要认证时填写。
- `BROWSER_FETCH_MCP_IMAGE` 和 `CHROMOTE_IMAGE`：需要固定镜像版本时，可以指定具体 tag，而不是使用 `latest`。
- 端口映射，例如 `127.0.0.1:8000:8000` 和 `127.0.0.1:8080:8080`：只有本地端口冲突时才需要修改。

启动本地服务：

```powershell
docker compose up -d
```

查看容器状态：

```powershell
docker compose ps
```

停止服务：

```powershell
docker compose down
```

只有在需要本地构建镜像，而不是使用已发布的 GHCR 镜像时，才使用开发 compose 文件：

```powershell
docker compose -f docker-compose.dev.yaml up -d --build
```

部署 compose 文件默认使用以下镜像：

- `ghcr.io/ghluuuuuu/browser-fetch-mcp:latest`
- `ghcr.io/ghluuuuuu/browser-fetch-mcp-chromote:latest`

可以通过 `BROWSER_FETCH_MCP_IMAGE` 或 `CHROMOTE_IMAGE` 指定要部署的镜像 tag。
