from __future__ import annotations

import contextlib

from playwright.async_api import Error as PlaywrightError


async def close_quietly(resource: object | None) -> None:
    if resource is None:
        return
    close = getattr(resource, "close", None)
    if close is None:
        return
    with contextlib.suppress(PlaywrightError):
        await close()
