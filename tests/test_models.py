import pytest

from browser_fetch_mcp.models import (
    make_fetch_result,
    slice_content,
    stringify_page_value,
    validate_http_url,
)


def test_slice_content_applies_start_and_limit() -> None:
    assert slice_content("abcdef", 2, 3) == ("cde", 6)


def test_slice_content_validates_inputs() -> None:
    with pytest.raises(ValueError):
        slice_content("abc", -1, 1)
    with pytest.raises(ValueError):
        slice_content("abc", 0, 0)


def test_make_fetch_result_has_lengths() -> None:
    result = make_fetch_result("https://example.com", "abcdef", 1, 2)

    assert result.ok is True
    assert result.content == "bc"
    assert result.content_length == 6
    assert result.returned_length == 2


def test_make_fetch_result_slices_links_and_images() -> None:
    result = make_fetch_result(
        "https://example.com",
        "content",
        0,
        10,
        links=[
            {"name": "One", "url": "https://example.com/1"},
            {"name": "Two", "url": "https://example.com/2"},
        ],
        links_start_index=1,
        links_max_length=1,
        images=[
            {"name": "A", "url": "https://example.com/a.png", "alt": "Alpha", "width": 640, "height": 480},
            {"name": "B", "url": "https://example.com/b.png", "alt": "", "width": None, "height": None},
        ],
        images_start_index=0,
        images_max_length=1,
    )

    assert result.links == [{"name": "Two", "url": "https://example.com/2"}]
    assert result.links_total == 2
    assert result.images == [
        {"name": "A", "url": "https://example.com/a.png", "alt": "Alpha", "width": 640, "height": 480}
    ]
    assert result.images_total == 2


def test_stringify_page_value_handles_non_strings() -> None:
    assert stringify_page_value(None) == ""
    assert stringify_page_value("abc") == "abc"
    assert stringify_page_value({"title": "Example"}) == "{'title': 'Example'}"


def test_validate_http_url_accepts_absolute_http_urls() -> None:
    assert validate_http_url("https://example.com") == "https://example.com"
    assert validate_http_url("http://example.com/path") == "http://example.com/path"


def test_validate_http_url_rejects_non_http_urls() -> None:
    with pytest.raises(ValueError, match="absolute http or https"):
        validate_http_url("ftp://example.com")
    with pytest.raises(ValueError, match="absolute http or https"):
        validate_http_url("/relative")
