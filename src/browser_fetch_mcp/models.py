from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class FetchResult(BaseModel):
    url: str
    ok: bool
    content: str = ""
    start_index: int
    max_length: int
    content_length: int = 0
    returned_length: int = 0
    links: list[dict[str, str]] = Field(default_factory=list)
    links_start_index: int = 0
    links_max_length: int = 50
    links_total: int = 0
    images: list[dict[str, str | int | None]] = Field(default_factory=list)
    images_start_index: int = 0
    images_max_length: int = 50
    images_total: int = 0
    error: str | None = None


class BatchFetchResult(BaseModel):
    results: list[FetchResult]


class SearchRow(BaseModel):
    title: str
    url: str


class SearchResult(BaseModel):
    keyword: str
    engine: str
    current_page: int = 1
    total_pages: int = 1
    rows: list[SearchRow]
    debug: dict[str, str | int | list[str]] | None = None


class ImageSearchItem(BaseModel):
    name: str
    url: str
    link_url: str | None = None
    width: int | None = None
    height: int | None = None


class ImageSearchResult(BaseModel):
    keyword: str
    engine: str
    current_page: int = 1
    total_pages: int = 1
    images: list[ImageSearchItem]
    debug: dict[str, str | int | list[str]] | None = None


def stringify_page_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def validate_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute http or https URL")
    return url


def slice_content(content: str, start_index: int, max_length: int) -> tuple[str, int]:
    if start_index < 0:
        raise ValueError("start_index must be greater than or equal to 0")
    if max_length < 1:
        raise ValueError("max_length must be greater than 0")
    return content[start_index : start_index + max_length], len(content)


def slice_items[T](items: list[T], start_index: int, max_length: int) -> tuple[list[T], int]:
    if start_index < 0:
        raise ValueError("item start_index must be greater than or equal to 0")
    if max_length < 0:
        raise ValueError("item max_length must be greater than or equal to 0")
    return items[start_index : start_index + max_length], len(items)


def make_fetch_result(
    url: str,
    content: str,
    start_index: int,
    max_length: int,
    *,
    links: list[dict[str, str]] | None = None,
    links_start_index: int = 0,
    links_max_length: int = 50,
    images: list[dict[str, str | int | None]] | None = None,
    images_start_index: int = 0,
    images_max_length: int = 50,
) -> FetchResult:
    sliced, content_length = slice_content(content, start_index, max_length)
    sliced_links, links_total = slice_items(links or [], links_start_index, links_max_length)
    sliced_images, images_total = slice_items(images or [], images_start_index, images_max_length)
    return FetchResult(
        url=url,
        ok=True,
        content=sliced,
        start_index=start_index,
        max_length=max_length,
        content_length=content_length,
        returned_length=len(sliced),
        links=sliced_links,
        links_start_index=links_start_index,
        links_max_length=links_max_length,
        links_total=links_total,
        images=sliced_images,
        images_start_index=images_start_index,
        images_max_length=images_max_length,
        images_total=images_total,
    )


def make_error_result(
    url: str,
    error: Exception | str,
    start_index: int,
    max_length: int,
    *,
    links_start_index: int = 0,
    links_max_length: int = 50,
    images_start_index: int = 0,
    images_max_length: int = 50,
) -> FetchResult:
    return FetchResult(
        url=url,
        ok=False,
        start_index=start_index,
        max_length=max_length,
        links_start_index=links_start_index,
        links_max_length=links_max_length,
        images_start_index=images_start_index,
        images_max_length=images_max_length,
        error=str(error),
    )
