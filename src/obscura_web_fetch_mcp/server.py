from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from .browser import BrowserClient
from .config import Settings, load_settings
from .models import BatchFetchResult
from .search import SearchService


def create_mcp(settings: Settings | None = None) -> FastMCP:
    resolved = settings or load_settings()
    browser = BrowserClient(resolved)
    search_service = SearchService(browser)
    mcp = FastMCP(
        "obscura-web-fetch",
        host=resolved.host,
        port=resolved.port,
        streamable_http_path="/mcp",
        sse_path="/sse",
        message_path="/messages/",
    )

    @mcp.tool(name="fetch")
    async def fetch_tool(
        url: str,
        start_index: int = 0,
        max_length: int = 20_000,
        exec_js: str = "",
        links_start_index: int = 0,
        links_max_length: int = 50,
        images_start_index: int = 0,
        images_max_length: int = 50,
    ) -> dict:
        """Fetch one page through CDP and return text plus page assets.

        Returns sliced page content, links, and images. Links contain name and url.
        Images contain name and url. Use links_start_index/links_max_length and
        images_start_index/images_max_length to page through large asset lists.
        """
        max_length = min(max_length, resolved.max_content_length)
        result = await browser.fetch(
            url,
            start_index=start_index,
            max_length=max_length,
            exec_js=exec_js,
            links_start_index=links_start_index,
            links_max_length=links_max_length,
            images_start_index=images_start_index,
            images_max_length=images_max_length,
        )
        return result.model_dump()

    @mcp.tool(name="batch-fetch")
    async def batch_fetch_tool(
        urls: list,
        start_index: int = 0,
        max_length: int = 20_000,
        exec_js: str = "",
        links_start_index: int = 0,
        links_max_length: int = 50,
        images_start_index: int = 0,
        images_max_length: int = 50,
    ) -> dict:
        """Fetch multiple pages through CDP and return text plus page assets for each URL.

        Each result includes sliced page content, links, and images. Use the links/images
        start and max parameters to limit returned asset list ranges.
        """
        if not urls:
            raise ValueError("urls must contain at least one URL")
        max_length = min(max_length, resolved.max_content_length)
        results = await browser.batch_fetch(
            urls,
            start_index=start_index,
            max_length=max_length,
            exec_js=exec_js,
            links_start_index=links_start_index,
            links_max_length=links_max_length,
            images_start_index=images_start_index,
            images_max_length=images_max_length,
        )
        return BatchFetchResult(results=results).model_dump()

    @mcp.tool(name="search")
    async def search_tool(
        keyword: str,
        engine: str = "auto",
        page: int = 1,
    ) -> dict:
        """Search the web and return candidate result links.
    This tool only discovers URLs and returns search metadata such as titles,
    snippets, and links. It does not open pages or retrieve full content.
    Critical rule:
    Do not use search snippets as the final source of truth. After finding useful
    URLs, call `fetch` for one page or `batchFetch` for multiple pages to read
    the actual page content. Final answers that require factual, current, or
    source-backed information should be based on fetched content, not snippets.
    Use cases:
    - Current/recent information, news, weather, prices, policies.
    - Official docs, API references, release notes, package versions.
    - Error messages, GitHub issues, Stack Overflow discussions.
    - Any task requiring external sources before answering.
    Engine selection:
    - Supported: "auto", "bing", "baidu", "google"; "bind" is treated as "bing".
    - Prefer "baidu" for Chinese or China-specific queries.
    - Prefer "google" or "bing" for non-Chinese/global technical queries.
    - If results are poor, retry with another engine, better keywords, or page > 1.
    - When using "bing", avoid spaces in `keyword`; whitespace is removed internally.
    Source selection:
    - Prefer official/primary sources: official docs, vendor docs, GitHub repos,
      release notes, government sites, official weather services, CVE/vendor advisories.
    - Use multiple sources for fast-changing or conflicting information.
    - If fetched content is blocked, empty, or irrelevant, try other result URLs.
    Args:
        keyword: Specific search keywords, including key error text, product/library name,
            version, location, date, or "official/docs/release notes" when useful.
        engine: Search engine to use: "auto", "bing", "baidu", or "google".
        page: Search result page number, starting at 1.
    Returns:
        Search result metadata with candidate URLs and pagination info.
        """
        result = await search_service.search(keyword, engine=engine or None, page=page)
        return result.model_dump()

    @mcp.tool(name="search_img")
    async def search_img_tool(
        keyword: str,
        engine: str = "auto",
        page: int = 1,
    ) -> dict:
        """Search internet images and return image result metadata.

        This tool searches image search pages through CDP and returns image names,
        image URLs, and pixel sizes when available. It does not fetch the target page
        content. Use "baidu" for Chinese image searches and "google" or "bing" for
        non-Chinese/global image searches. If one engine returns weak results, retry
        with another engine or page > 1.

        Args:
            keyword: Image search keywords.
            engine: Image search engine: "auto", "bing", "baidu", or "google".
            page: Image search page number, starting at 1.
        """
        result = await search_service.search_img(keyword, engine=engine or None, page=page)
        return result.model_dump()

    return mcp


def create_app(settings: Settings | None = None) -> Starlette:
    mcp = create_mcp(settings)
    streamable_http_app = mcp.streamable_http_app()
    sse_app = mcp.sse_app()

    return Starlette(
        debug=mcp.settings.debug,
        routes=[*streamable_http_app.routes, *sse_app.routes],
        middleware=[*streamable_http_app.user_middleware, *sse_app.user_middleware],
        lifespan=lambda app: mcp.session_manager.run(),
    )


def main() -> None:
    settings = load_settings()
    app = create_app(settings)

    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )
