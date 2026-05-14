from playwright.async_api import Error as PlaywrightError

from obscura_web_fetch_mcp.playwright_utils import close_quietly


class BrokenResource:
    async def close(self) -> None:
        raise PlaywrightError("Target page, context or browser has been closed")


async def test_close_quietly_suppresses_playwright_close_errors() -> None:
    await close_quietly(BrokenResource())
