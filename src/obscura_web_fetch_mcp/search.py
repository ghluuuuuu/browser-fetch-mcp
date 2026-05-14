from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import re
from urllib.parse import quote, quote_plus

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from .browser import BrowserClient
from .config import SearchEngine
from .models import ImageSearchItem, ImageSearchResult, SearchResult, SearchRow
from .playwright_utils import close_quietly


def build_search_extract_js(selectors: list[str]) -> str:
    encoded_selectors = json.dumps(selectors)
    script = """
() => {
  const rows = [];
  const seen = new Set();
  const selectors = __SELECTORS__;
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      const anchor = node.matches?.('a[href]')
        ? node
        : node.closest('a[href]') || node.querySelector?.('a[href]');
      const rawUrl = anchor?.getAttribute('href') || '';
      const title = (node.innerText || anchor?.innerText || '').trim();
      let url = rawUrl;
      if (rawUrl.startsWith('/url?')) {
        const target = new URL(rawUrl, location.href).searchParams.get('q');
        if (target) url = target;
      }
      if (!title || !url || seen.has(url)) continue;
      if (!/^https?:\\/\\//i.test(url)) continue;
      seen.add(url);
      rows.push({title, url});
    }
  }
  const pageNumbers = [];
  for (const node of document.querySelectorAll('#b_pages a, #page a, #foot a, #botstuff a, a[aria-label^="Page "], a[aria-label^="第"]')) {
    const text = (node.innerText || node.textContent || '').trim();
    const label = node.getAttribute('aria-label') || '';
    const value = Number.parseInt(text || label.replace(/\\D+/g, ''), 10);
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
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      const img = node.matches?.('img') ? node : node.querySelector?.('img');
      const meta = readMeta(node.closest?.('[data-m], [m]') || node);
      const anchor = node.matches?.('a[href]') ? node : node.closest?.('a[href]') || node.querySelector?.('a[href]');
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
      const url = rawUrl.startsWith('//') ? `https:${rawUrl}` : rawUrl;
      const linkUrl = rawLinkUrl.startsWith('//') ? `https:${rawLinkUrl}` : rawLinkUrl;
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


def parse_search_rows(raw_rows: object) -> list[SearchRow]:
    if not isinstance(raw_rows, list):
        return []

    rows: list[SearchRow] = []
    seen: set[str] = set()
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url or url in seen:
            continue
        if not url.lower().startswith(("http://", "https://")):
            continue
        seen.add(url)
        rows.append(SearchRow(title=title, url=url))
    return rows


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

    async def search(self, keyword: str, engine: str | None = None, page: int = 1) -> SearchResult:
        if not keyword.strip():
            raise ValueError("keyword must not be empty")
        selected = normalize_engine(engine, self.browser.settings.default_search_engine)
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")

        adapter = ADAPTERS[selected]
        search_url = adapter.build_url(keyword, page=page)
        raw_payload = await self._evaluate_search(search_url, adapter.build_extract_js(), adapter.selectors)
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
        rows = parse_search_rows(raw_rows)
        return SearchResult(
            keyword=keyword,
            engine=selected,
            current_page=page,
            total_pages=max(page, total_pages),
            rows=rows,
            debug=debug if not rows else None,
        )

    async def _evaluate_search(self, url: str, extract_js: str, selectors: list[str]) -> object:
        browser = None
        context = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(self.browser.settings.cdp_endpoint)
                context = await browser.new_context()
                page = await context.new_page()
                page.set_default_navigation_timeout(self.browser.settings.navigation_timeout_ms)
                page.set_default_timeout(self.browser.settings.navigation_timeout_ms)
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.browser.settings.navigation_timeout_ms,
                )
                selector = ", ".join(selectors)
                try:
                    await page.wait_for_selector(
                        selector,
                        timeout=min(10_000, self.browser.settings.navigation_timeout_ms),
                    )
                except PlaywrightError:
                    pass
                await page.evaluate(
                    """async () => {
                      for (let index = 0; index < 4; index += 1) {
                        window.scrollTo(0, document.body.scrollHeight);
                        await new Promise((resolve) => setTimeout(resolve, 350));
                      }
                    }"""
                )
                rows = []
                deadline = asyncio.get_running_loop().time() + min(
                    10,
                    self.browser.settings.navigation_timeout_ms / 1000,
                )
                while asyncio.get_running_loop().time() < deadline:
                    rows = await page.evaluate(extract_js)
                    if rows:
                        break
                    await asyncio.sleep(0.5)
                if rows:
                    return rows
                return {
                    "rows": [],
                    "images": [],
                    "totalPages": 1,
                    "title": await page.title(),
                    "bodyTextSample": await page.evaluate(
                        "() => (document.body && document.body.innerText || '').slice(0, 500)"
                    ),
                }
        finally:
            await close_quietly(context)
            await close_quietly(browser)

    async def search_img(self, keyword: str, engine: str | None = None, page: int = 1) -> ImageSearchResult:
        if not keyword.strip():
            raise ValueError("keyword must not be empty")
        selected = normalize_engine(engine, self.browser.settings.default_search_engine)
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")

        adapter = IMAGE_ADAPTERS[selected]
        search_url = adapter.build_url(keyword, page=page)
        raw_payload = await self._evaluate_search(search_url, adapter.build_extract_js(), adapter.selectors)
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
