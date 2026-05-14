from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from time import monotonic

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from .config import Settings
from .browser_context import create_browser_context
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
({includeLinks, includeImages}) => {
  const cleanText = (value) => (value || '').replace(/\s+/g, ' ').trim();
  const isUsefulLabel = (value) => {
    const text = cleanText(value);
    return text.length > 0 && text.length <= 240;
  };
  const firstUsefulText = (values) => {
    for (const value of values) {
      const text = cleanText(value);
      if (isUsefulLabel(text)) return text;
    }
    return '';
  };
  const directLabel = (node) => {
    if (!node) return '';
    const descendants = node.querySelectorAll
      ? [...node.querySelectorAll('img[alt], [aria-label], [title]')]
      : [];
    return firstUsefulText([
      node.innerText,
      node.textContent,
      node.getAttribute && node.getAttribute('aria-label'),
      node.getAttribute && node.getAttribute('title'),
      node.getAttribute && node.getAttribute('alt'),
      ...descendants.map((child) => (
        child.getAttribute('alt') ||
        child.getAttribute('aria-label') ||
        child.getAttribute('title') ||
        ''
      )),
    ]);
  };
  const contextualLabel = (node) => {
    let current = node && node.parentElement;
    let depth = 0;
    while (current && depth < 4 && current !== document.body && current !== document.documentElement) {
      const titleNode = current.querySelector(
        '[aria-label], [title], h1, h2, h3, h4, h5, h6, figcaption, .title, .name'
      );
      const fromTitleNode = directLabel(titleNode);
      if (fromTitleNode) return fromTitleNode;

      const currentText = firstUsefulText([current.innerText, current.textContent]);
      if (currentText) return currentText;

      current = current.parentElement;
      depth += 1;
    }
    return '';
  };
  const labelFor = (node) => directLabel(node) || contextualLabel(node);
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
  const links = includeLinks ? unique([...document.querySelectorAll('a[href]')].map((node) => ({
    name: labelFor(node),
    url: node.href || '',
  })).filter((item) => /^https?:\/\//i.test(item.url))) : [];
  const images = includeImages ? unique([...document.querySelectorAll('img[src], img[data-src]')].map((node) => {
    const label = labelFor(node);
    return {
      alt: firstUsefulText([node.getAttribute('alt'), label]),
      name: label,
      url: node.currentSrc || node.src || node.getAttribute('data-src') || '',
      width: node.naturalWidth || node.width || null,
      height: node.naturalHeight || node.height || null,
    };
  }).filter((item) => /^https?:\/\//i.test(item.url))) : [];
  return {links, images};
}
"""

RENDERED_CONTENT_PROBE_JS = r"""
() => {
  const bodyText = document.body && document.body.innerText;
  const rootText = document.documentElement && document.documentElement.innerText;
  const text = bodyText || rootText || "";
  const links = document.querySelectorAll('a[href]').length;
  const images = document.querySelectorAll('img[src], img[data-src]').length;
  return {
    textLength: text.trim().length,
    links,
    images,
  };
}
"""

CONTENT_READY_TIMEOUT_MS = 3_000
CONTENT_READY_POLL_INTERVAL_MS = 250
CONTENT_READY_STABLE_SAMPLES = 2
AUTO_SCROLL_STEP_PX = 800
AUTO_SCROLL_SETTLE_MS = 250

AUTO_SCROLL_JS = """
async ({maxDistance, step, settleMs}) => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const limit = Math.max(0, Number(maxDistance) || 0);
  const increment = Math.max(1, Number(step) || 1);
  let travelled = 0;
  let lastHeight = document.documentElement.scrollHeight || document.body.scrollHeight || 0;

  while (travelled < limit) {
    const remaining = limit - travelled;
    const distance = Math.min(increment, remaining);
    window.scrollBy(0, distance);
    travelled += distance;
    await sleep(settleMs);

    const scrollTop = window.scrollY || document.documentElement.scrollTop || document.body.scrollTop || 0;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const currentHeight = document.documentElement.scrollHeight || document.body.scrollHeight || 0;
    const atBottom = scrollTop + viewportHeight >= currentHeight - 2;
    const heightChanged = currentHeight !== lastHeight;
    lastHeight = currentHeight;

    if (atBottom && !heightChanged) {
      break;
    }
  }

  return {
    distance: travelled,
    scrollHeight: document.documentElement.scrollHeight || document.body.scrollHeight || 0,
    scrollY: window.scrollY || document.documentElement.scrollTop || document.body.scrollTop || 0,
  };
}
"""


@dataclass(frozen=True)
class RenderedContentSignal:
    text_length: int = 0
    links: int = 0
    images: int = 0

    @property
    def has_content(self) -> bool:
        return self.text_length > 0 or self.links > 0 or self.images > 0

    @property
    def signature(self) -> tuple[int, int, int]:
        return (self.text_length, self.links, self.images)


def _coerce_non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int | float):
        return max(0, int(value))
    return 0


async def read_rendered_content_signal(page) -> RenderedContentSignal:
    value = await page.evaluate(RENDERED_CONTENT_PROBE_JS)
    if not isinstance(value, dict):
        return RenderedContentSignal()
    return RenderedContentSignal(
        text_length=_coerce_non_negative_int(value.get("textLength")),
        links=_coerce_non_negative_int(value.get("links")),
        images=_coerce_non_negative_int(value.get("images")),
    )


async def wait_for_rendered_content(
    page,
    *,
    timeout_ms: int,
    poll_interval_ms: int = CONTENT_READY_POLL_INTERVAL_MS,
    stable_samples: int = CONTENT_READY_STABLE_SAMPLES,
) -> RenderedContentSignal:
    deadline = monotonic() + max(timeout_ms, 0) / 1000
    interval = max(poll_interval_ms, 0) / 1000
    required_samples = max(stable_samples, 1)
    last_signature: tuple[int, int, int] | None = None
    matching_samples = 0
    last_signal = RenderedContentSignal()

    while True:
        signal = await read_rendered_content_signal(page)
        last_signal = signal

        if signal.has_content:
            if signal.signature == last_signature:
                matching_samples += 1
            else:
                last_signature = signal.signature
                matching_samples = 1
            if matching_samples >= required_samples:
                return signal
        else:
            last_signature = None
            matching_samples = 0

        remaining = deadline - monotonic()
        if remaining <= 0:
            return last_signal
        await asyncio.sleep(min(interval, remaining))


async def auto_scroll_page(page, *, max_distance: int) -> None:
    if max_distance <= 0:
        return
    await page.evaluate(
        AUTO_SCROLL_JS,
        {
            "maxDistance": max_distance,
            "step": AUTO_SCROLL_STEP_PX,
            "settleMs": AUTO_SCROLL_SETTLE_MS,
        },
    )
    await wait_for_rendered_content(page, timeout_ms=CONTENT_READY_TIMEOUT_MS)


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
        include_links: bool = False,
        include_images: bool = False,
        auto_scroll: bool = False,
        auto_scroll_max_distance: int = 0,
    ) -> FetchResult:
        validate_http_url(url)
        if start_index < 0:
            raise ValueError("start_index must be greater than or equal to 0")
        if max_length < 1:
            raise ValueError("max_length must be greater than 0")
        if auto_scroll_max_distance < 0:
            raise ValueError("auto_scroll_max_distance must be greater than or equal to 0")

        browser = None
        context = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(self.settings.cdp_endpoint)
                context = await create_browser_context(browser, self.settings)
                page = await context.new_page()
                page.set_default_navigation_timeout(self.settings.navigation_timeout_ms)
                page.set_default_timeout(self.settings.navigation_timeout_ms)
                await page.goto(url, wait_until="domcontentloaded", timeout=self.settings.navigation_timeout_ms)
                await wait_for_rendered_content(
                    page,
                    timeout_ms=min(self.settings.navigation_timeout_ms, CONTENT_READY_TIMEOUT_MS),
                )
                if auto_scroll:
                    await auto_scroll_page(page, max_distance=auto_scroll_max_distance)
                expression = exec_js.strip() if exec_js else DEFAULT_TEXT_JS
                value = await page.evaluate(expression)
                assets = await page.evaluate(
                    PAGE_ASSETS_JS,
                    {
                        "includeLinks": include_links,
                        "includeImages": include_images,
                    },
                )
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
        include_links: bool = False,
        include_images: bool = False,
        auto_scroll: bool = False,
        auto_scroll_max_distance: int = 0,
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
                    include_links=include_links,
                    include_images=include_images,
                    auto_scroll=auto_scroll,
                    auto_scroll_max_distance=auto_scroll_max_distance,
                )

        return list(await asyncio.gather(*(fetch_one(url) for url in urls)))
