import secrets
from typing import Annotated
from urllib.parse import parse_qs

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .browser import BrowserClient
from .config import Settings, load_settings
from .models import BatchFetchResult
from .search import SearchService


class AccessKeyMiddleware:
    def __init__(self, app: ASGIApp, access_key: str):
        self.app = app
        self.access_key = access_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._is_authorized(scope):
            await self.app(scope, receive, send)
            return

        response = JSONResponse({"error": "Unauthorized"}, status_code=401)
        await response(scope, receive, send)

    def _is_authorized(self, scope: Scope) -> bool:
        expected = self.access_key
        if not expected:
            return True

        provided = self._header_value(scope, b"x-api-key")
        authorization = self._header_value(scope, b"authorization")
        if authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() == "bearer":
                provided = token

        if not provided:
            provided = self._query_param(scope, "api_key")

        return bool(provided) and secrets.compare_digest(provided, expected)

    @staticmethod
    def _header_value(scope: Scope, name: bytes) -> str:
        for header_name, header_value in scope.get("headers", []):
            if header_name.lower() == name:
                return header_value.decode("latin-1").strip()
        return ""

    @staticmethod
    def _query_param(scope: Scope, name: str) -> str:
        raw_query = scope.get("query_string", b"").decode("latin-1")
        return parse_qs(raw_query).get(name, [""])[0].strip()


def create_mcp(settings: Settings | None = None) -> FastMCP:
    resolved = settings or load_settings()
    browser = BrowserClient(resolved)
    search_service = SearchService(browser)
    mcp = FastMCP(
        "browser-fetch",
        host=resolved.host,
        port=resolved.port,
        streamable_http_path="/mcp",
        sse_path="/sse",
        message_path="/messages/",
    )

    @mcp.tool(name="fetch")
    async def fetch_tool(
        url: Annotated[str, Field(description="Absolute http or https URL to fetch.")],
        start_index: Annotated[
            int,
            Field(description="Zero-based content start offset for slicing returned text."),
        ] = 0,
        max_length: Annotated[
            int,
            Field(description="Maximum number of content characters to return."),
        ] = 20_000,
        exec_js: Annotated[
            str,
            Field(description="Optional JavaScript expression to evaluate instead of default text extraction."),
        ] = "",
        links_start_index: Annotated[
            int,
            Field(description="Zero-based start offset for the returned link list."),
        ] = 0,
        links_max_length: Annotated[
            int,
            Field(description="Maximum number of links to return. Use 0 to return no link items."),
        ] = 50,
        images_start_index: Annotated[
            int,
            Field(description="Zero-based start offset for the returned image list."),
        ] = 0,
        images_max_length: Annotated[
            int,
            Field(description="Maximum number of images to return. Use 0 to return no image items."),
        ] = 50,
        include_links: Annotated[
            bool,
            Field(description="Whether to extract the page link list. Enable when links are needed."),
        ] = False,
        include_images: Annotated[
            bool,
            Field(description="Whether to extract the page image list. Enable when images are needed."),
        ] = False,
        auto_scroll: Annotated[
            bool,
            Field(description="Whether to scroll down before extracting content and assets."),
        ] = False,
        auto_scroll_max_distance: Annotated[
            int,
            Field(description="Maximum downward scroll distance in pixels for lazy-loaded pages."),
        ] = 0,
    ) -> dict:
        """Get the content of a specified web page.

        Returns sliced page content, links, and images. Links contain name and url.
        Images contain name, url, alt, width, and height. If content from multiple
        pages is needed, prefer batch-fetch instead of calling fetch repeatedly.
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
            include_links=include_links,
            include_images=include_images,
            auto_scroll=auto_scroll,
            auto_scroll_max_distance=auto_scroll_max_distance,
        )
        return result.model_dump()

    @mcp.tool(name="batch-fetch")
    async def batch_fetch_tool(
        urls: Annotated[list[str], Field(description="Absolute http or https URLs to fetch.")],
        start_index: Annotated[
            int,
            Field(description="Zero-based content start offset for slicing returned text."),
        ] = 0,
        max_length: Annotated[
            int,
            Field(description="Maximum number of content characters to return per URL."),
        ] = 20_000,
        exec_js: Annotated[
            str,
            Field(description="Optional JavaScript expression to evaluate on each page."),
        ] = "",
        links_start_index: Annotated[
            int,
            Field(description="Zero-based start offset for each returned link list."),
        ] = 0,
        links_max_length: Annotated[
            int,
            Field(description="Maximum number of links to return per URL. Use 0 for no link items."),
        ] = 50,
        images_start_index: Annotated[
            int,
            Field(description="Zero-based start offset for each returned image list."),
        ] = 0,
        images_max_length: Annotated[
            int,
            Field(description="Maximum number of images to return per URL. Use 0 for no image items."),
        ] = 50,
        include_links: Annotated[
            bool,
            Field(description="Whether to extract page link lists. Enable when links are needed."),
        ] = False,
        include_images: Annotated[
            bool,
            Field(description="Whether to extract page image lists. Enable when images are needed."),
        ] = False,
        auto_scroll: Annotated[
            bool,
            Field(description="Whether to scroll each page before extracting content and assets."),
        ] = False,
        auto_scroll_max_distance: Annotated[
            int,
            Field(description="Maximum downward scroll distance in pixels for lazy-loaded pages."),
        ] = 0,
    ) -> dict:
        """Get the content of multiple specified web pages.

        Prefer this tool when content from multiple web pages is needed. Each result
        includes sliced page content, links, and images.
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
            include_links=include_links,
            include_images=include_images,
            auto_scroll=auto_scroll,
            auto_scroll_max_distance=auto_scroll_max_distance,
        )
        return BatchFetchResult(results=results).model_dump()

    @mcp.tool(name="search")
    async def search_tool(
        keyword: Annotated[
            str,
            Field(
                description=(
                    "Search keywords. Include key error text, product/library name, version, "
                    "location, date, or official/docs/release-notes qualifiers when useful."
                ),
            ),
        ],
        engine: Annotated[
            str,
            Field(
                description=(
                    'Search engine: "auto", "bing", "baidu", or "google"; "bind" is treated '
                    'as "bing". Prefer baidu for Chinese or China-specific queries, and google '
                    "or bing for non-Chinese/global technical queries."
                ),
            ),
        ] = "auto",
        page: Annotated[
            int,
            Field(description="Search result page number, starting at 1. Try page > 1 for more results."),
        ] = 1,
        context_mode: Annotated[
            str | None,
            Field(
                description=(
                    'Search context mode: "none" returns title/url only, "snippet" returns search-result '
                    'snippets without opening result pages, "preview" fetches bounded context for top results, '
                    'and "full" fetches context for every result.'
                ),
            ),
        ] = None,
        context_top_k: Annotated[
            int,
            Field(description="Maximum number of top search results to fetch when context_mode is preview."),
        ] = 3,
        context_max_length: Annotated[
            int,
            Field(description="Maximum number of fetched context characters per search result preview."),
        ] = 1_000,
        enable_show_link_context: Annotated[
            bool | None,
            Field(
                description=(
                    "Deprecated compatibility flag. When context_mode is omitted, true maps to full fetched "
                    "context and false maps to snippet-only discovery. Prefer context_mode."
                ),
            ),
        ] = None,
    ) -> dict:
        """Search the web and return candidate result links.

    This tool discovers URLs and returns titles, links, and search-result snippets
    by default without opening each result page. Use context_mode="preview" for
    bounded top-result page previews or context_mode="full" for the legacy eager
    fetched-context behavior.
    Critical rule:
    Do not use search metadata alone as the final source of truth. If the preview
    is insufficient, call `fetch` for one page or `batchFetch` for multiple pages
    to read more actual page content.
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
        """
        result = await search_service.search(
            keyword,
            engine=engine or None,
            page=page,
            enable_show_link_context=enable_show_link_context,
            context_mode=context_mode,
            context_top_k=context_top_k,
            context_max_length=min(context_max_length, resolved.max_content_length),
        )
        return result.model_dump()

    @mcp.tool(name="search_img")
    async def search_img_tool(
        keyword: Annotated[str, Field(description="Image search keywords.")],
        engine: Annotated[
            str,
            Field(
                description=(
                    'Image search engine: "auto", "bing", "baidu", or "google". Prefer baidu '
                    "for Chinese image searches, and google or bing for non-Chinese/global images."
                ),
            ),
        ] = "auto",
        page: Annotated[
            int,
            Field(description="Image search result page number, starting at 1."),
        ] = 1,
    ) -> dict:
        """Search internet images and return image result metadata.

        This tool searches image search pages through CDP and returns image names,
        image URLs, source page URLs, and pixel sizes when available. The returned
        `images[].url` values are suitable for Markdown image previews, for example
        `![name](url)`, but search engines may return thumbnail or cached image URLs.
        When the user needs the original image, call `fetch` on the corresponding
        `images[].link_url` source page when present, then inspect that page for the
        original image URL. If no source page is available, call `fetch` on the image
        URL itself to verify what it actually resolves to before presenting it as an
        original image.
        """
        result = await search_service.search_img(keyword, engine=engine or None, page=page)
        return result.model_dump()

    return mcp


def create_app(settings: Settings | None = None) -> ASGIApp:
    resolved = settings or load_settings()
    mcp = create_mcp(resolved)
    streamable_http_app = mcp.streamable_http_app()
    sse_app = mcp.sse_app()

    app = Starlette(
        debug=mcp.settings.debug,
        routes=[*streamable_http_app.routes, *sse_app.routes],
        middleware=[*streamable_http_app.user_middleware, *sse_app.user_middleware],
        lifespan=lambda app: mcp.session_manager.run(),
    )
    if resolved.access_key:
        return AccessKeyMiddleware(app, resolved.access_key)
    return app


def main() -> None:
    settings = load_settings()
    app = create_app(settings)

    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )
