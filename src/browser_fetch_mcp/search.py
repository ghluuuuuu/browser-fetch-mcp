from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import random
import re
from typing import Literal
from urllib.parse import parse_qs, quote, quote_plus, urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from .browser import BrowserClient
from .browser_context import create_browser_context
from .config import SearchEngine
from .models import ImageSearchItem, ImageSearchResult, SearchResult, SearchRow
from .playwright_utils import close_quietly


HOMEPAGE_INTERACTION_ENGINES = {"bing"}
BING_HOME_URL = "https://www.bing.com/"
DEFAULT_SEARCH_CONTEXT_MAX_LENGTH = 1_000
SearchContextMode = Literal["none", "snippet", "preview", "full"]
BING_SEARCH_INPUT_SELECTORS = [
    'textarea[name="q"]',
    'input[name="q"]',
    '#sb_form_q',
    'textarea[aria-label="Enter your search term"]',
    'input[aria-label="Enter your search term"]',
    'textarea[aria-label="Search"]',
    'input[aria-label="Search"]',
]
BING_SEARCH_BUTTON_SELECTORS = [
    '#search_icon',
    'input[type="submit"][value="Search"]',
    'button[type="submit"]',
    'label[for="sb_form_go"]',
]
BING_IMAGES_TAB_SELECTORS = [
    'a[href*="/images/search"]',
    'a[href*="scope=images"]',
    'a:has-text("Images")',
    'a:has-text("图片")',
    'a:has-text("圖片")',
]
SEARCH_HOME_URLS = {
    "bing": BING_HOME_URL,
}
SEARCH_INPUT_SELECTORS = {
    "bing": BING_SEARCH_INPUT_SELECTORS,
}
SEARCH_BUTTON_SELECTORS = {
    "bing": BING_SEARCH_BUTTON_SELECTORS,
}
IMAGE_TAB_SELECTORS = {
    "bing": BING_IMAGES_TAB_SELECTORS,
}


@dataclass(frozen=True)
class SearchPacing:
    pre_navigation_delay_ms: tuple[int, int] = (0, 0)
    post_navigation_delay_ms: tuple[int, int] = (0, 0)
    selector_timeout_ms: int = 10_000
    scroll_steps: int = 4
    scroll_pause_ms: tuple[int, int] = (350, 350)
    poll_interval_ms: tuple[int, int] = (500, 500)
    incremental_scroll: bool = False


DEFAULT_SEARCH_PACING = SearchPacing()


def pacing_for_engine(engine: SearchEngine | None) -> SearchPacing:
    return DEFAULT_SEARCH_PACING


async def sleep_random_ms(delay_range: tuple[int, int]) -> None:
    lower, upper = delay_range
    if upper <= 0:
        return
    await asyncio.sleep(random.uniform(max(0, lower), max(lower, upper)) / 1000)


async def scroll_search_results(page, pacing: SearchPacing) -> None:
    if not pacing.incremental_scroll:
        await page.evaluate(
            """async () => {
              for (let index = 0; index < 4; index += 1) {
                window.scrollTo(0, document.body.scrollHeight);
                await new Promise((resolve) => setTimeout(resolve, 350));
              }
            }"""
        )
        return

    for _ in range(max(0, pacing.scroll_steps)):
        await page.evaluate(
            """() => {
              const viewport = window.innerHeight || document.documentElement.clientHeight || 800;
              window.scrollBy(0, Math.max(320, Math.floor(viewport * 0.75)));
            }"""
        )
        await sleep_random_ms(pacing.scroll_pause_ms)


async def find_first_visible_locator(page, selectors: list[str]):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count() > 0 and await locator.is_visible():
                return locator
        except PlaywrightError:
            continue
    return None


async def fill_search_input(locator, text: str, pacing: SearchPacing) -> None:
    try:
        await locator.click()
    except PlaywrightError:
        await locator.focus()
    await sleep_random_ms(pacing.poll_interval_ms)
    await locator.fill(text)


async def submit_home_search(page, engine: SearchEngine, keyword: str, pacing: SearchPacing) -> None:
    input_locator = await find_first_visible_locator(page, SEARCH_INPUT_SELECTORS[engine])
    if input_locator is None:
        raise PlaywrightError(f"{engine} search input was not visible")

    await fill_search_input(input_locator, keyword, pacing)
    await sleep_random_ms(pacing.poll_interval_ms)

    button_locator = await find_first_visible_locator(page, SEARCH_BUTTON_SELECTORS[engine])
    if button_locator is not None:
        async with page.expect_navigation(wait_until="domcontentloaded"):
            await button_locator.click()
        return

    async with page.expect_navigation(wait_until="domcontentloaded"):
        await input_locator.press("Enter")


async def open_image_results(page, engine: SearchEngine, target_url: str, pacing: SearchPacing):
    await sleep_random_ms(pacing.poll_interval_ms)
    images_tab = await find_first_visible_locator(page, IMAGE_TAB_SELECTORS[engine])
    if images_tab is None:
        await page.goto(target_url, wait_until="domcontentloaded")
        return page

    if engine == "bing":
        try:
            async with page.expect_popup(timeout=5_000) as popup_info:
                await images_tab.click()
            popup_page = await popup_info.value
            await popup_page.wait_for_load_state("domcontentloaded")
            return popup_page
        except PlaywrightError:
            if is_image_results_url(engine, page.url):
                return page

    async with page.expect_navigation(wait_until="domcontentloaded"):
        await images_tab.click()
    return page


def google_result_page_index(url: str) -> int:
    params = parse_qs(urlparse(url).query)
    start = params.get("start", ["0"])[0]
    try:
        return max(1, int(start) // 10 + 1)
    except ValueError:
        return 1


def is_google_images_url(url: str) -> bool:
    params = parse_qs(urlparse(url).query)
    return params.get("tbm") == ["isch"] or params.get("udm") == ["2"]


def is_bing_images_url(url: str) -> bool:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return "/images/search" in parsed.path or params.get("scope") == ["images"]


def is_image_results_url(engine: SearchEngine, url: str) -> bool:
    if engine == "google":
        return is_google_images_url(url)
    if engine == "bing":
        return is_bing_images_url(url)
    return False


def build_search_extract_js(selectors: list[str]) -> str:
    encoded_selectors = json.dumps(selectors)
    script = r"""
() => {
  const rows = [];
  const seen = new Set();
  const selectors = __SELECTORS__;
  const cleanText = (value) => (value || '').replace(/\s+/g, ' ').trim();
  const findContainer = (node) => (
    node.closest?.('.b_algo, .g, .result, .c-container, li') || node.parentElement || node
  );
  const findSnippet = (node, title) => {
    const container = findContainer(node);
    const snippetSelectors = [
      '.b_caption p', '.b_caption', '.VwiC3b', '.IsZvec',
      '.aCOpRe', '.c-abstract', '.c-span-last', '.content-right_8Zs40'
    ];
    for (const snippetSelector of snippetSelectors) {
      const snippetNode = container.querySelector?.(snippetSelector);
      const text = cleanText(snippetNode?.innerText || snippetNode?.textContent || '');
      if (text && text !== title) return text;
    }
    const text = cleanText(container.innerText || container.textContent || '');
    if (!text || text === title) return '';
    return cleanText(text.replace(title, '')).slice(0, 500);
  };
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      const anchor = node.matches?.('a[href]')
        ? node
        : node.closest('a[href]') || node.querySelector?.('a[href]');
      const rawUrl = anchor?.getAttribute('href') || '';
      const title = cleanText(node.innerText || anchor?.innerText || '');
      let url = rawUrl;
      if (rawUrl.startsWith('/url?')) {
        const target = new URL(rawUrl, location.href).searchParams.get('q');
        if (target) url = target;
      }
      if (!title || !url || seen.has(url)) continue;
      if (!/^https?:\/\//i.test(url)) continue;
      seen.add(url);
      rows.push({title, url, snippet: findSnippet(node, title)});
    }
  }
  const pageNumbers = [];
  for (const node of document.querySelectorAll('#b_pages a, #page a, #foot a, #botstuff a, a[aria-label^="Page "], a[aria-label^="第"]')) {
    const text = (node.innerText || node.textContent || '').trim();
    const label = node.getAttribute('aria-label') || '';
    const value = Number.parseInt(text || label.replace(/\D+/g, ''), 10);
    if (Number.isFinite(value)) pageNumbers.push(value);
  }
  return {
    rows,
    totalPages: pageNumbers.length ? Math.max(...pageNumbers) : 1,
  };
}
"""
    return script.replace("__SELECTORS__", encoded_selectors)


def build_image_extract_js(selectors: list[str]) -> str:
    encoded_selectors = json.dumps(selectors)
    script = r"""
() => {
  const images = [];
  const seen = new Set();
  const selectors = __SELECTORS__;
  const readMeta = (node) => {
    const metadataText = node.getAttribute('data-m') || node.getAttribute('m') || '';
    if (!metadataText) return {};
    try {
      return JSON.parse(metadataText);
    } catch {
      return {};
    }
  };
  const normalizeUrl = (rawUrl) => {
    if (!rawUrl) return '';
    const withProtocol = rawUrl.startsWith('//') ? `https:${rawUrl}` : rawUrl;
    try {
      return new URL(withProtocol, location.href).href;
    } catch {
      return withProtocol;
    }
  };
  const findOuterAnchor = (node, img) => {
    let current = img || node;
    for (let depth = 0; current && depth < 8; depth += 1) {
      if (current.matches?.('a[href]')) return current;
      const nestedAnchor = current.querySelector?.('a[href]');
      if (nestedAnchor) return nestedAnchor;
      current = current.parentElement;
    }
    return node.matches?.('a[href]') ? node : node.closest?.('a[href]') || node.querySelector?.('a[href]') || null;
  };
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      const img = node.matches?.('img') ? node : node.querySelector?.('img');
      const meta = readMeta(node.closest?.('[data-m], [m]') || node);
      const anchor = findOuterAnchor(node, img);
      const rawUrl = meta.murl || meta.imgurl || meta.ou || node.getAttribute('data-src') || img?.currentSrc || img?.src || '';
      const rawLinkUrl = meta.purl || meta.surl || meta.ru || anchor?.href || '';
      const name = (
        meta.t ||
        meta.pt ||
        img?.getAttribute('alt') ||
        img?.getAttribute('title') ||
        node.getAttribute('aria-label') ||
        node.innerText ||
        ''
      ).trim();
      const width = Number.parseInt(meta.w || meta.width || img?.naturalWidth || img?.width || 0, 10) || null;
      const height = Number.parseInt(meta.h || meta.height || img?.naturalHeight || img?.height || 0, 10) || null;
      const url = normalizeUrl(rawUrl);
      const linkUrl = normalizeUrl(rawLinkUrl);
      if (!url || seen.has(url)) continue;
      if (!/^https?:\/\//i.test(url)) continue;
      seen.add(url);
      images.push({name, url, link_url: /^https?:\/\//i.test(linkUrl) ? linkUrl : null, width, height});
    }
  }
  const pageNumbers = [];
  for (const node of document.querySelectorAll('#b_pages a, #page a, #foot a, #botstuff a, a[aria-label^="Page "], a[aria-label^="第"]')) {
    const text = (node.innerText || node.textContent || '').trim();
    const label = node.getAttribute('aria-label') || '';
    const value = Number.parseInt(text || label.replace(/\D+/g, ''), 10);
    if (Number.isFinite(value)) pageNumbers.push(value);
  }
  return {
    images,
    totalPages: pageNumbers.length ? Math.max(...pageNumbers) : 1,
  };
}
"""
    return script.replace("__SELECTORS__", encoded_selectors)


@dataclass(frozen=True)
class SearchAdapter:
    name: SearchEngine
    url_template: str
    selectors: list[str]
    page_param: str | None = None
    page_size: int = 10
    page_base: int = 0
    space_as_plus: bool = True
    remove_keyword_spaces: bool = False

    def build_url(self, keyword: str, page: int = 1) -> str:
        if self.remove_keyword_spaces:
            keyword = re.sub(r"\s+", "", keyword)
        if self.space_as_plus:
            encoded_keyword = quote_plus(keyword, safe="")
        else:
            encoded_keyword = quote(keyword, safe="")
        url = self.url_template.format(keyword=encoded_keyword)
        if page > 1 and self.page_param:
            page_value = self.page_base + (page - 1) * self.page_size
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{self.page_param}={page_value}"
        return url

    def build_extract_js(self) -> str:
        return build_search_extract_js(self.selectors)


@dataclass(frozen=True)
class ImageSearchAdapter:
    name: SearchEngine
    url_template: str
    selectors: list[str]
    page_param: str | None = None
    page_size: int = 20
    page_base: int = 0
    space_as_plus: bool = True
    remove_keyword_spaces: bool = False

    def build_url(self, keyword: str, page: int = 1) -> str:
        if self.remove_keyword_spaces:
            keyword = re.sub(r"\s+", "", keyword)
        if self.space_as_plus:
            encoded_keyword = quote_plus(keyword, safe="")
        else:
            encoded_keyword = quote(keyword, safe="")
        url = self.url_template.format(keyword=encoded_keyword)
        if page > 1 and self.page_param:
            page_value = self.page_base + (page - 1) * self.page_size
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{self.page_param}={page_value}"
        return url

    def build_extract_js(self) -> str:
        return build_image_extract_js(self.selectors)


ADAPTERS: dict[str, SearchAdapter] = {
    "baidu": SearchAdapter(
        "baidu",
        "https://www.baidu.com/s?wd={keyword}",
        [
            "#content_left .c-container h3 a[href]",
            "#content_left .result h3 a[href]",
            "#content_left .c-container a[href]",
        ],
        "pn",
        10,
        0,
    ),
    "google": SearchAdapter(
        "google",
        "https://www.google.com/search?q={keyword}",
        [
            "#search a[href] h3",
            "#rso a[href] h3",
            "div.g a[href] h3",
        ],
        "start",
        10,
        0,
    ),
    "bing": SearchAdapter(
        "bing",
        "https://cn.bing.com/search?q={keyword}",
        [
            "#b_results .b_algo h2 a[href]",
            "#b_results li.b_algo h2 a[href]",
            "#b_results .b_algo .b_title a[href]",
            "#b_results .b_algo a[href]",
            "main .b_algo h2 a[href]",
        ],
        "first",
        10,
        1,
        False,
        True,
    ),
}


IMAGE_ADAPTERS: dict[str, ImageSearchAdapter] = {
    "baidu": ImageSearchAdapter(
        "baidu",
        "https://image.baidu.com/search/index?tn=baiduimage&word={keyword}",
        [
            "img[src]",
            "img[data-src]",
        ],
        "pn",
        30,
        0,
    ),
    "google": ImageSearchAdapter(
        "google",
        "https://www.google.com/search?tbm=isch&q={keyword}",
        [
            "img[src]",
            "img[data-src]",
        ],
        "ijn",
        1,
        0,
    ),
    "bing": ImageSearchAdapter(
        "bing",
        "https://cn.bing.com/images/search?q={keyword}",
        [
            "a.iusc",
            ".iusc",
            "img.mimg",
        ],
        "first",
        35,
        1,
        False,
        True,
    ),
}


def normalize_engine(engine: str | None, default_engine: SearchEngine) -> SearchEngine:
    selected = (engine or default_engine).strip().lower()
    if selected in {"", "auto"}:
        selected = default_engine
    if selected == "bind":
        selected = "bing"
    if selected not in ADAPTERS:
        supported = "auto, " + ", ".join(sorted(ADAPTERS))
        raise ValueError(f"Unsupported search engine '{engine}'. Supported engines: {supported}")
    return selected  # type: ignore[return-value]


def parse_search_rows(raw_rows: object, *, include_snippet: bool = True) -> list[SearchRow]:
    if not isinstance(raw_rows, list):
        return []

    rows: list[SearchRow] = []
    seen: set[str] = set()
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or "").strip() if include_snippet else ""
        if not title or not url or url in seen:
            continue
        if not url.lower().startswith(("http://", "https://")):
            continue
        seen.add(url)
        rows.append(SearchRow(title=title, url=url, snippet=snippet))
    return rows


def normalize_context_mode(
    context_mode: str | None,
    enable_show_link_context: bool | None,
) -> SearchContextMode:
    if context_mode is not None:
        selected = context_mode.strip().lower()
        if selected not in {"none", "snippet", "preview", "full"}:
            raise ValueError("context_mode must be one of: none, snippet, preview, full")
        return selected  # type: ignore[return-value]
    if enable_show_link_context is True:
        return "full"
    return "snippet"


def parse_image_rows(raw_rows: object) -> list[ImageSearchItem]:
    if not isinstance(raw_rows, list):
        return []

    images: list[ImageSearchItem] = []
    seen: set[str] = set()
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        if not url.lower().startswith(("http://", "https://")):
            continue
        seen.add(url)
        name = str(item.get("name") or "").strip()
        width = item.get("width")
        height = item.get("height")
        images.append(
            ImageSearchItem(
                name=name,
                url=url,
                link_url=str(item.get("link_url") or "").strip() or None,
                width=width if isinstance(width, int) else None,
                height=height if isinstance(height, int) else None,
            )
        )
    return images


class SearchService:
    def __init__(self, browser: BrowserClient):
        self.browser = browser

    async def search(
        self,
        keyword: str,
        engine: str | None = None,
        page: int = 1,
        *,
        enable_show_link_context: bool | None = None,
        context_mode: str | None = None,
        context_top_k: int = 3,
        context_max_length: int = DEFAULT_SEARCH_CONTEXT_MAX_LENGTH,
    ) -> SearchResult:
        if not keyword.strip():
            raise ValueError("keyword must not be empty")
        selected = normalize_engine(engine, self.browser.settings.default_search_engine)
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        selected_context_mode = normalize_context_mode(context_mode, enable_show_link_context)
        if context_top_k < 0:
            raise ValueError("context_top_k must be greater than or equal to 0")
        if context_max_length < 1:
            raise ValueError("context_max_length must be greater than 0")

        adapter = ADAPTERS[selected]
        search_url = adapter.build_url(keyword, page=page)
        raw_payload = await self._evaluate_search(
            search_url,
            adapter.build_extract_js(),
            adapter.selectors,
            engine=selected,
            keyword=keyword,
            page=page,
        )
        if isinstance(raw_payload, dict):
            raw_rows = raw_payload.get("rows")
            total_pages = int(raw_payload.get("totalPages") or 1)
            debug = {
                "url": search_url,
                "selectors": adapter.selectors,
                "title": str(raw_payload.get("title") or ""),
                "bodyTextSample": str(raw_payload.get("bodyTextSample") or ""),
                "totalPages": total_pages,
            }
        else:
            raw_rows = raw_payload
            total_pages = 1
            debug = None
        rows = parse_search_rows(raw_rows, include_snippet=selected_context_mode != "none")
        if selected_context_mode == "none":
            rows = [row.model_copy(update={"context_status": "skipped"}) for row in rows]
        if rows and selected_context_mode in {"preview", "full"}:
            rows = await self._add_link_context(
                rows,
                top_k=context_top_k if selected_context_mode == "preview" else len(rows),
                max_length=context_max_length,
            )
        return SearchResult(
            keyword=keyword,
            engine=selected,
            current_page=page,
            total_pages=max(page, total_pages),
            rows=rows,
            debug=debug if not rows else None,
        )

    async def _add_link_context(
        self,
        rows: list[SearchRow],
        *,
        top_k: int,
        max_length: int,
    ) -> list[SearchRow]:
        selected_rows = rows[:top_k]
        skipped_rows = rows[top_k:]
        if not selected_rows:
            return [row.model_copy(update={"context_status": "skipped"}) for row in rows]
        results = await self.browser.batch_fetch(
            [row.url for row in selected_rows],
            start_index=0,
            max_length=max_length,
        )
        enriched_rows = []
        for row, result in zip(selected_rows, results, strict=True):
            if getattr(result, "ok", True):
                enriched_rows.append(
                    row.model_copy(update={"context": result.content, "context_status": "fetched"})
                )
                continue
            error = str(getattr(result, "error", "") or "").lower()
            status = "timeout" if "timeout" in error or "timed out" in error else "error"
            enriched_rows.append(row.model_copy(update={"context": "", "context_status": status}))
        return [
            *enriched_rows,
            *(row.model_copy(update={"context_status": "skipped"}) for row in skipped_rows),
        ]

    async def _evaluate_search(
        self,
        url: str,
        extract_js: str,
        selectors: list[str],
        *,
        engine: SearchEngine | None = None,
        keyword: str | None = None,
        page: int = 1,
        image_search: bool = False,
    ) -> object:
        pacing = pacing_for_engine(engine)
        return await self._evaluate_search_with_pacing(
            url,
            extract_js,
            selectors,
            pacing,
            engine=engine,
            keyword=keyword,
            page=page,
            image_search=image_search,
        )

    async def _evaluate_search_with_pacing(
        self,
        url: str,
        extract_js: str,
        selectors: list[str],
        pacing: SearchPacing,
        *,
        engine: SearchEngine | None = None,
        keyword: str | None = None,
        page: int = 1,
        image_search: bool = False,
    ) -> object:
        browser = None
        context = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(self.browser.settings.cdp_endpoint)
                context = await create_browser_context(browser, self.browser.settings)
                browser_page = await context.new_page()
                browser_page.set_default_navigation_timeout(self.browser.settings.navigation_timeout_ms)
                browser_page.set_default_timeout(self.browser.settings.navigation_timeout_ms)
                await sleep_random_ms(pacing.pre_navigation_delay_ms)
                if engine in HOMEPAGE_INTERACTION_ENGINES and keyword:
                    browser_page = await self._navigate_home_search(
                        browser_page,
                        engine,
                        keyword,
                        url,
                        page,
                        image_search,
                        pacing,
                    )
                else:
                    await browser_page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self.browser.settings.navigation_timeout_ms,
                    )
                await sleep_random_ms(pacing.post_navigation_delay_ms)
                selector = ", ".join(selectors)
                try:
                    await browser_page.wait_for_selector(
                        selector,
                        timeout=min(pacing.selector_timeout_ms, self.browser.settings.navigation_timeout_ms),
                    )
                except PlaywrightError:
                    pass
                await scroll_search_results(browser_page, pacing)
                rows = []
                deadline = asyncio.get_running_loop().time() + min(
                    10,
                    self.browser.settings.navigation_timeout_ms / 1000,
                )
                while asyncio.get_running_loop().time() < deadline:
                    rows = await browser_page.evaluate(extract_js)
                    if rows:
                        break
                    await sleep_random_ms(pacing.poll_interval_ms)
                if rows:
                    return rows
                return {
                    "rows": [],
                    "images": [],
                    "totalPages": 1,
                    "title": await browser_page.title(),
                    "bodyTextSample": await browser_page.evaluate(
                        "() => (document.body && document.body.innerText || '').slice(0, 500)"
                    ),
                }
        finally:
            await close_quietly(context)
            await close_quietly(browser)

    async def _navigate_home_search(
        self,
        page,
        engine: SearchEngine,
        keyword: str,
        target_url: str,
        target_page: int,
        image_search: bool,
        pacing: SearchPacing,
    ):
        await page.goto(
            SEARCH_HOME_URLS[engine],
            wait_until="domcontentloaded",
            timeout=self.browser.settings.navigation_timeout_ms,
        )
        await sleep_random_ms(pacing.post_navigation_delay_ms)
        await submit_home_search(page, engine, keyword, pacing)
        await sleep_random_ms(pacing.post_navigation_delay_ms)
        if image_search and not is_image_results_url(engine, page.url):
            page = await open_image_results(page, engine, target_url, pacing)
            await sleep_random_ms(pacing.post_navigation_delay_ms)
        current_page = google_result_page_index(page.url)
        if target_page > 1 and current_page != target_page:
            await page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=self.browser.settings.navigation_timeout_ms,
            )
        return page

    async def search_img(self, keyword: str, engine: str | None = None, page: int = 1) -> ImageSearchResult:
        if not keyword.strip():
            raise ValueError("keyword must not be empty")
        selected = normalize_engine(engine, self.browser.settings.default_search_engine)
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")

        adapter = IMAGE_ADAPTERS[selected]
        search_url = adapter.build_url(keyword, page=page)
        raw_payload = await self._evaluate_search(
            search_url,
            adapter.build_extract_js(),
            adapter.selectors,
            engine=selected,
            keyword=keyword,
            page=page,
            image_search=True,
        )
        if isinstance(raw_payload, dict):
            raw_rows = raw_payload.get("images")
            total_pages = int(raw_payload.get("totalPages") or 1)
            debug = {
                "url": search_url,
                "selectors": adapter.selectors,
                "title": str(raw_payload.get("title") or ""),
                "bodyTextSample": str(raw_payload.get("bodyTextSample") or ""),
                "totalPages": total_pages,
            }
        else:
            raw_rows = raw_payload
            total_pages = 1
            debug = None
        images = parse_image_rows(raw_rows)
        return ImageSearchResult(
            keyword=keyword,
            engine=selected,
            current_page=page,
            total_pages=max(page, total_pages),
            images=images,
            debug=debug if not images else None,
        )
