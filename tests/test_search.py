from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from browser_fetch_mcp.search import (
    ADAPTERS,
    IMAGE_ADAPTERS,
    SearchService,
    pacing_for_engine,
    parse_image_rows,
    normalize_engine,
    parse_search_rows,
)


def test_normalize_engine_defaults_and_alias() -> None:
    assert normalize_engine(None, "bing") == "bing"
    assert normalize_engine("auto", "baidu") == "baidu"
    assert normalize_engine("bind", "google") == "bing"


def test_normalize_engine_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported search engine"):
        normalize_engine("duckduckgo", "bing")


def test_bing_build_url_removes_spaces_and_percent_encodes_query() -> None:
    url = ADAPTERS["bing"].build_url("福州 天气 当前 预报")

    assert url == "https://cn.bing.com/search?q=%E7%A6%8F%E5%B7%9E%E5%A4%A9%E6%B0%94%E5%BD%93%E5%89%8D%E9%A2%84%E6%8A%A5"


def test_google_build_url_keeps_plus_for_spaces() -> None:
    url = ADAPTERS["google"].build_url("hello world")

    assert url == "https://www.google.com/search?q=hello+world"


def test_bing_image_build_url_removes_spaces() -> None:
    url = IMAGE_ADAPTERS["bing"].build_url("福州 图片")

    assert url == "https://cn.bing.com/images/search?q=%E7%A6%8F%E5%B7%9E%E5%9B%BE%E7%89%87"


def test_bing_build_url_adds_page_index() -> None:
    url = ADAPTERS["bing"].build_url("福州天气 今天", page=3)

    assert url.endswith("&first=21")


def test_parse_search_rows_filters_invalid_and_deduplicates() -> None:
    rows = parse_search_rows(
        [
            {"title": "One", "url": "https://example.com/1"},
            {"title": "", "url": "https://example.com/empty"},
            {"title": "Duplicate", "url": "https://example.com/1"},
            {"title": "Images", "url": "/images/search?q=test"},
            {"title": "Two", "url": "https://example.com/2"},
        ],
    )

    assert [row.model_dump() for row in rows] == [
        {"title": "One", "url": "https://example.com/1"},
        {"title": "Two", "url": "https://example.com/2"},
    ]


def test_parse_search_rows_returns_all_valid_rows() -> None:
    rows = parse_search_rows(
        [
            {"title": "One", "url": "https://example.com/1"},
            {"title": "Two", "url": "https://example.com/2"},
        ],
    )

    assert len(rows) == 2


def test_parse_image_rows_filters_and_keeps_dimensions() -> None:
    rows = parse_image_rows(
        [
            {"name": "One", "url": "https://example.com/1.jpg", "width": 640, "height": 480},
            {"name": "Bad", "url": "/relative.jpg", "width": 1, "height": 1},
            {"name": "Duplicate", "url": "https://example.com/1.jpg", "width": 320, "height": 240},
            {
                "name": "Two",
                "url": "https://example.com/2.jpg",
                "link_url": "https://example.com/page",
                "width": 800,
                "height": 600,
            },
        ]
    )

    assert [row.model_dump() for row in rows] == [
        {
            "name": "One",
            "url": "https://example.com/1.jpg",
            "link_url": None,
            "width": 640,
            "height": 480,
        },
        {
            "name": "Two",
            "url": "https://example.com/2.jpg",
            "link_url": "https://example.com/page",
            "width": 800,
            "height": 600,
        },
    ]


def test_parse_search_rows_from_static_html_fixture() -> None:
    html = Path("tests/fixtures/search_results.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    raw_rows = [
        {"title": anchor.get_text(strip=True), "url": anchor.get("href", "")}
        for anchor in soup.select(".b_algo a[href], .result a[href], .c-container a[href]")
    ]

    rows = parse_search_rows(raw_rows)

    assert [row.model_dump() for row in rows] == [
        {"title": "Bing Result", "url": "https://example.com/bing"},
        {"title": "Alpha Result", "url": "https://example.com/alpha"},
        {"title": "Beta Result", "url": "https://example.com/beta"},
        {"title": "Gamma Result", "url": "https://example.com/gamma"},
    ]


def test_bing_adapter_selectors_skip_header_navigation() -> None:
    html = Path("tests/fixtures/search_results.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    raw_rows = [
        {"title": anchor.get_text(strip=True), "url": anchor.get("href", "")}
        for selector in ADAPTERS["bing"].selectors
        for anchor in soup.select(selector)
    ]

    rows = parse_search_rows(raw_rows)

    assert [row.model_dump() for row in rows] == [
        {"title": "Bing Result", "url": "https://example.com/bing"}
    ]


def test_search_extract_js_has_valid_arrow_function() -> None:
    script = ADAPTERS["bing"].build_extract_js()

    assert script.lstrip().startswith("() => {")
    assert "() => {{" not in script


def test_search_extract_js_reads_google_pagination() -> None:
    script = ADAPTERS["google"].build_extract_js()

    assert "#botstuff a" in script
    assert 'a[aria-label^="Page "]' in script


def test_image_extract_js_reads_image_metadata() -> None:
    script = IMAGE_ADAPTERS["bing"].build_extract_js()

    assert "images" in script
    assert "link_url" in script
    assert "width" in script
    assert "height" in script


def test_google_search_uses_slower_pacing() -> None:
    google = pacing_for_engine("google")
    bing = pacing_for_engine("bing")

    assert google.incremental_scroll is True
    assert google.pre_navigation_delay_ms[0] > bing.pre_navigation_delay_ms[0]
    assert google.post_navigation_delay_ms[0] > bing.post_navigation_delay_ms[0]
    assert google.poll_interval_ms[0] > bing.poll_interval_ms[0]


class FakeSettings:
    cdp_endpoint = "ws://127.0.0.1:9222"
    navigation_timeout_ms = 2_000
    default_search_engine = "bing"


class FakeBrowser:
    settings = FakeSettings()


async def test_evaluate_search_retries_until_rows(monkeypatch) -> None:
    calls = {"evaluate": 0}

    class FakePage:
        def set_default_navigation_timeout(self, timeout):
            pass

        def set_default_timeout(self, timeout):
            pass

        async def goto(self, *args, **kwargs):
            return None

        async def wait_for_selector(self, *args, **kwargs):
            return None

        async def evaluate(self, expression):
            calls["evaluate"] += 1
            if calls["evaluate"] == 1:
                return []
            return {
                "rows": [{"title": "Result", "url": "https://example.com"}],
                "totalPages": 9,
            }

        async def title(self):
            return ""

    class FakeContext:
        async def new_page(self):
            return FakePage()

        async def close(self):
            return None

    class FakeChromium:
        async def connect_over_cdp(self, endpoint):
            return FakeBrowserConnection()

    class FakeBrowserConnection:
        async def new_context(self):
            return FakeContext()

        async def close(self):
            return None

    class FakePlaywright:
        chromium = FakeChromium()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr("browser_fetch_mcp.search.async_playwright", lambda: FakePlaywright())

    service = SearchService(FakeBrowser())  # type: ignore[arg-type]
    payload = await service._evaluate_search(
        "https://cn.bing.com/search?q=x",
        "() => []",
        ["#b_results"],
        engine="bing",
    )

    assert payload == {"rows": [{"title": "Result", "url": "https://example.com"}], "totalPages": 9}
    assert calls["evaluate"] == 2


async def test_search_returns_page_metadata(monkeypatch) -> None:
    async def fake_evaluate_search(self, url, extract_js, selectors, *, engine=None):
        assert url.endswith("&first=21")
        assert engine == "bing"
        return {
            "rows": [{"title": "Result", "url": "https://example.com"}],
            "totalPages": 9,
        }

    monkeypatch.setattr(SearchService, "_evaluate_search", fake_evaluate_search)

    service = SearchService(FakeBrowser())  # type: ignore[arg-type]
    result = await service.search("福州天气 今天", engine="bing", page=3)

    assert result.current_page == 3
    assert result.total_pages == 9
    assert result.rows[0].url == "https://example.com"


async def test_search_img_returns_image_metadata(monkeypatch) -> None:
    async def fake_evaluate_search(self, url, extract_js, selectors, *, engine=None):
        assert "/images/search" in url
        assert engine == "bing"
        return {
            "images": [
                {
                    "name": "Image",
                    "url": "https://example.com/image.jpg",
                    "link_url": "https://example.com/page",
                    "width": 800,
                    "height": 600,
                }
            ],
            "totalPages": 4,
        }

    monkeypatch.setattr(SearchService, "_evaluate_search", fake_evaluate_search)

    service = SearchService(FakeBrowser())  # type: ignore[arg-type]
    result = await service.search_img("福州 图片", engine="bing", page=1)

    assert result.current_page == 1
    assert result.total_pages == 4
    assert result.images[0].model_dump() == {
        "name": "Image",
        "url": "https://example.com/image.jpg",
        "link_url": "https://example.com/page",
        "width": 800,
        "height": 600,
    }
