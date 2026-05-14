from __future__ import annotations

import asyncio
from collections.abc import Sequence

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from .config import Settings
from .models import FetchResult, make_error_result, make_fetch_result, stringify_page_value, validate_http_url
from .playwright_utils import close_quietly

DEFAULT_TEXT_JS = """
() => {
  const bodyText = document.body && document.body.innerText;
  const rootText = document.documentElement && document.documentElement.innerText;
  return bodyText || rootText || "";
}
"""

PAGE_ASSETS_JS = r"""
() => {
  const unique = (items) => {
    const seen = new Set();
    const output = [];
    for (const item of items) {
      const key = item.url || "";
      if (!key || seen.has(key)) continue;
      seen.add(key);
      output.push(item);
    }
    return output;
  };
  const links = unique([...document.querySelectorAll('a[href]')].map((node) => ({
    name: (node.innerText || node.getAttribute('aria-label') || node.getAttribute('title') || '').trim(),
    url: node.href || '',
  })).filter((item) => /^https?:\/\//i.test(item.url)));
  const images = unique([...document.querySelectorAll('img[src], img[data-src]')].map((node) => ({
    name: (node.getAttribute('alt') || node.getAttribute('title') || node.getAttribute('aria-label') || '').trim(),
    url: node.currentSrc || node.src || node.getAttribute('data-src') || '',
  })).filter((item) => /^https?:\/\//i.test(item.url)));
  return {links, images};
}
"""


class BrowserClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def fetch(
        self,
        url: str,
        *,
        start_index: int,
        max_length: int,
        exec_js: str | None = None,
        links_start_index: int = 0,
        links_max_length: int = 50,
        images_start_index: int = 0,
        images_max_length: int = 50,
    ) -> FetchResult:
        validate_http_url(url)
        if start_index < 0:
            raise ValueError("start_index must be greater than or equal to 0")
        if max_length < 1:
            raise ValueError("max_length must be greater than 0")

        browser = None
        context = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(self.settings.cdp_endpoint)
                context = await browser.new_context()
                page = await context.new_page()
                page.set_default_navigation_timeout(self.settings.navigation_timeout_ms)
                page.set_default_timeout(self.settings.navigation_timeout_ms)
                await page.goto(url, wait_until="domcontentloaded", timeout=self.settings.navigation_timeout_ms)
                expression = exec_js.strip() if exec_js else DEFAULT_TEXT_JS
                value = await page.evaluate(expression)
                assets = await page.evaluate(PAGE_ASSETS_JS)
                return make_fetch_result(
                    url,
                    stringify_page_value(value),
                    start_index,
                    max_length,
                    links=assets.get("links", []) if isinstance(assets, dict) else [],
                    links_start_index=links_start_index,
                    links_max_length=links_max_length,
                    images=assets.get("images", []) if isinstance(assets, dict) else [],
                    images_start_index=images_start_index,
                    images_max_length=images_max_length,
                )
        except PlaywrightError as exc:
            return make_error_result(
                url,
                exc,
                start_index,
                max_length,
                links_start_index=links_start_index,
                links_max_length=links_max_length,
                images_start_index=images_start_index,
                images_max_length=images_max_length,
            )
        finally:
            await close_quietly(context)
            await close_quietly(browser)

    async def batch_fetch(
        self,
        urls: Sequence[str],
        *,
        start_index: int,
        max_length: int,
        exec_js: str | None = None,
        links_start_index: int = 0,
        links_max_length: int = 50,
        images_start_index: int = 0,
        images_max_length: int = 50,
    ) -> list[FetchResult]:
        semaphore = asyncio.Semaphore(self.settings.batch_concurrency)

        async def fetch_one(url: str) -> FetchResult:
            async with semaphore:
                return await self.fetch(
                    url,
                    start_index=start_index,
                    max_length=max_length,
                    exec_js=exec_js,
                    links_start_index=links_start_index,
                    links_max_length=links_max_length,
                    images_start_index=images_start_index,
                    images_max_length=images_max_length,
                )

        return list(await asyncio.gather(*(fetch_one(url) for url in urls)))
