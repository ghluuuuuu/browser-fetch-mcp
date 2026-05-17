from pathlib import Path

from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
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


@pytest.fixture(autouse=True)
def fake_search_browser_context(monkeypatch):
    async def create_context(browser, settings=None):
        return await browser.new_context()

    monkeypatch.setattr("browser_fetch_mcp.search.create_browser_context", create_context)


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
        {"title": "One", "url": "https://example.com/1", "context": ""},
        {"title": "Two", "url": "https://example.com/2", "context": ""},
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
        {"title": "Bing Result", "url": "https://example.com/bing", "context": ""},
        {"title": "Alpha Result", "url": "https://example.com/alpha", "context": ""},
        {"title": "Beta Result", "url": "https://example.com/beta", "context": ""},
        {"title": "Gamma Result", "url": "https://example.com/gamma", "context": ""},
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
        {"title": "Bing Result", "url": "https://example.com/bing", "context": ""}
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


def test_google_search_uses_default_pacing() -> None:
    google = pacing_for_engine("google")
    bing = pacing_for_engine("bing")

    assert google == bing
    assert google.incremental_scroll is False
    assert google.pre_navigation_delay_ms == (0, 0)
    assert google.post_navigation_delay_ms == (0, 0)


class FakeSettings:
    cdp_endpoint = "ws://127.0.0.1:9222"
    navigation_timeout_ms = 2_000
    default_search_engine = "bing"


class FakeBrowser:
    settings = FakeSettings()

    async def batch_fetch(self, urls, *, start_index, max_length, **kwargs):
        del start_index, kwargs

        class Result:
            def __init__(self, url):
                self.content = f"preview for {url}"[:max_length]

        return [Result(url) for url in urls]


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


async def test_google_search_opens_search_url_directly(monkeypatch) -> None:
    actions = []

    class FakeNavigation:
        async def __aenter__(self):
            actions.append(("expect_navigation",))
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeLocator:
        def __init__(self, page, selector):
            self.page = page
            self.selector = selector
            self.first = self

        async def count(self):
            return 1 if self.selector == 'textarea[name="q"]' or self.selector == 'input[name="btnK"]' else 0

        async def is_visible(self):
            return True

        async def click(self):
            actions.append(("click", self.selector))
            if self.selector == 'input[name="btnK"]':
                self.page.url = "https://www.google.com/search?q=hello+world"

        async def focus(self):
            actions.append(("focus", self.selector))

        async def fill(self, value):
            actions.append(("fill", self.selector, value))

        async def type(self, value, delay=0):
            actions.append(("type", self.selector, value))

        async def press(self, key):
            actions.append(("press", self.selector, key))
            self.page.url = "https://www.google.com/search?q=hello+world"

    class FakePage:
        url = "about:blank"

        def set_default_navigation_timeout(self, timeout):
            pass

        def set_default_timeout(self, timeout):
            pass

        def locator(self, selector):
            return FakeLocator(self, selector)

        def expect_navigation(self, **kwargs):
            return FakeNavigation()

        def expect_popup(self, **kwargs):
            return FakePopupTimeout()

        async def goto(self, url, *args, **kwargs):
            actions.append(("goto", url))
            self.url = url

        async def wait_for_selector(self, *args, **kwargs):
            return None

        async def evaluate(self, expression):
            if "window.scrollBy" in expression:
                return None
            return {
                "rows": [{"title": "Result", "url": "https://example.com"}],
                "totalPages": 1,
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
    monkeypatch.setattr("browser_fetch_mcp.search.sleep_random_ms", lambda delay_range: _noop())
    service = SearchService(FakeBrowser())  # type: ignore[arg-type]
    payload = await service._evaluate_search(
        "https://www.google.com/search?q=hello+world",
        "() => []",
        ["#search a[href] h3"],
        engine="google",
        keyword="hello world",
    )

    assert payload == {"rows": [{"title": "Result", "url": "https://example.com"}], "totalPages": 1}
    assert ("goto", "https://www.google.com/search?q=hello+world") in actions
    assert not any(action[0] in {"click", "fill", "type", "press"} for action in actions)


async def test_google_image_search_opens_search_url_directly(monkeypatch) -> None:
    actions = []

    class FakeNavigation:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakePopupTimeout:
        async def __aenter__(self):
            raise PlaywrightTimeoutError("no popup")

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeLocator:
        def __init__(self, page, selector):
            self.page = page
            self.selector = selector
            self.first = self

        async def count(self):
            visible_selectors = {
                'textarea[name="q"]',
                'input[name="btnK"]',
                'a[href*="tbm=isch"]',
            }
            return 1 if self.selector in visible_selectors else 0

        async def is_visible(self):
            return True

        async def click(self):
            actions.append(("click", self.selector))
            if self.selector == 'input[name="btnK"]':
                self.page.url = "https://www.google.com/search?q=images"
            if self.selector == 'a[href*="tbm=isch"]':
                self.page.url = "https://www.google.com/search?q=images&tbm=isch"

        async def focus(self):
            pass

        async def fill(self, value):
            pass

        async def type(self, value, delay=0):
            pass

        async def press(self, key):
            pass

    class FakePage:
        url = "about:blank"

        def set_default_navigation_timeout(self, timeout):
            pass

        def set_default_timeout(self, timeout):
            pass

        def locator(self, selector):
            return FakeLocator(self, selector)

        def expect_navigation(self, **kwargs):
            return FakeNavigation()

        def expect_popup(self, **kwargs):
            return FakePopupTimeout()

        async def goto(self, url, *args, **kwargs):
            actions.append(("goto", url))
            self.url = url

        async def wait_for_selector(self, *args, **kwargs):
            return None

        async def evaluate(self, expression):
            if "window.scrollBy" in expression:
                return None
            return {
                "images": [{"name": "Image", "url": "https://example.com/image.jpg"}],
                "totalPages": 1,
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
    monkeypatch.setattr("browser_fetch_mcp.search.sleep_random_ms", lambda delay_range: _noop())
    service = SearchService(FakeBrowser())  # type: ignore[arg-type]
    payload = await service._evaluate_search(
        "https://www.google.com/search?tbm=isch&q=images",
        "() => []",
        ["img[src]"],
        engine="google",
        keyword="images",
        image_search=True,
    )

    assert payload == {"images": [{"name": "Image", "url": "https://example.com/image.jpg"}], "totalPages": 1}
    assert ("goto", "https://www.google.com/search?tbm=isch&q=images") in actions
    assert not any(action[0] == "click" for action in actions)


async def test_bing_search_opens_homepage_and_submits_query(monkeypatch) -> None:
    actions = []

    class FakeNavigation:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakePopupTimeout:
        async def __aenter__(self):
            raise PlaywrightTimeoutError("no popup")

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeLocator:
        def __init__(self, page, selector):
            self.page = page
            self.selector = selector
            self.first = self

        async def count(self):
            return 1 if self.selector == 'input[name="q"]' or self.selector == "#search_icon" else 0

        async def is_visible(self):
            return True

        async def click(self):
            actions.append(("click", self.selector))
            if self.selector == "#search_icon":
                self.page.url = "https://www.bing.com/search?q=hello+world"

        async def focus(self):
            actions.append(("focus", self.selector))

        async def fill(self, value):
            actions.append(("fill", self.selector, value))

        async def type(self, value, delay=0):
            actions.append(("type", self.selector, value))

        async def press(self, key):
            actions.append(("press", self.selector, key))
            self.page.url = "https://www.bing.com/search?q=hello+world"

    class FakePage:
        url = "about:blank"

        def set_default_navigation_timeout(self, timeout):
            pass

        def set_default_timeout(self, timeout):
            pass

        def locator(self, selector):
            return FakeLocator(self, selector)

        def expect_navigation(self, **kwargs):
            return FakeNavigation()

        def expect_popup(self, **kwargs):
            return FakePopupTimeout()

        async def goto(self, url, *args, **kwargs):
            actions.append(("goto", url))
            self.url = url

        async def wait_for_selector(self, *args, **kwargs):
            return None

        async def evaluate(self, expression):
            if "window.scrollTo" in expression:
                return None
            return {
                "rows": [{"title": "Bing Result", "url": "https://example.com/bing"}],
                "totalPages": 1,
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
    monkeypatch.setattr("browser_fetch_mcp.search.sleep_random_ms", lambda delay_range: _noop())
    service = SearchService(FakeBrowser())  # type: ignore[arg-type]
    payload = await service._evaluate_search(
        "https://cn.bing.com/search?q=helloworld",
        "() => []",
        ["#b_results .b_algo h2 a[href]"],
        engine="bing",
        keyword="hello world",
    )

    assert payload == {"rows": [{"title": "Bing Result", "url": "https://example.com/bing"}], "totalPages": 1}
    assert actions[:2] == [
        ("goto", "https://www.bing.com/"),
        ("click", 'input[name="q"]'),
    ]
    assert ("fill", 'input[name="q"]', "hello world") in actions
    assert not any(action[0] == "type" for action in actions)
    assert ("click", "#search_icon") in actions


async def test_bing_image_search_clicks_images_tab(monkeypatch) -> None:
    actions = []

    class FakeNavigation:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakePopupTimeout:
        async def __aenter__(self):
            raise PlaywrightTimeoutError("no popup")

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeLocator:
        def __init__(self, page, selector):
            self.page = page
            self.selector = selector
            self.first = self

        async def count(self):
            visible_selectors = {
                'input[name="q"]',
                "#search_icon",
                'a[href*="/images/search"]',
            }
            return 1 if self.selector in visible_selectors else 0

        async def is_visible(self):
            return True

        async def click(self):
            actions.append(("click", self.selector))
            if self.selector == "#search_icon":
                self.page.url = "https://www.bing.com/search?q=images"
            if self.selector == 'a[href*="/images/search"]':
                self.page.url = "https://www.bing.com/images/search?q=images"

        async def focus(self):
            pass

        async def fill(self, value):
            pass

        async def type(self, value, delay=0):
            pass

        async def press(self, key):
            pass

    class FakePage:
        url = "about:blank"

        def set_default_navigation_timeout(self, timeout):
            pass

        def set_default_timeout(self, timeout):
            pass

        def locator(self, selector):
            return FakeLocator(self, selector)

        def expect_navigation(self, **kwargs):
            return FakeNavigation()

        def expect_popup(self, **kwargs):
            return FakePopupTimeout()

        async def goto(self, url, *args, **kwargs):
            actions.append(("goto", url))
            self.url = url

        async def wait_for_selector(self, *args, **kwargs):
            return None

        async def evaluate(self, expression):
            if "window.scrollTo" in expression:
                return None
            return {
                "images": [{"name": "Image", "url": "https://example.com/bing-image.jpg"}],
                "totalPages": 1,
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
    monkeypatch.setattr("browser_fetch_mcp.search.sleep_random_ms", lambda delay_range: _noop())

    service = SearchService(FakeBrowser())  # type: ignore[arg-type]
    payload = await service._evaluate_search(
        "https://cn.bing.com/images/search?q=images",
        "() => []",
        ["img.mimg"],
        engine="bing",
        keyword="images",
        image_search=True,
    )

    assert payload == {"images": [{"name": "Image", "url": "https://example.com/bing-image.jpg"}], "totalPages": 1}
    assert ("goto", "https://www.bing.com/") in actions
    assert ("click", 'a[href*="/images/search"]') in actions


async def test_bing_image_search_uses_popup_page(monkeypatch) -> None:
    actions = []

    class FakeNavigation:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakePopupInfo:
        def __init__(self, popup_page):
            self._popup_page = popup_page
            self.value = self._value()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def _value(self):
            return self._popup_page

    class FakeLocator:
        def __init__(self, page, selector):
            self.page = page
            self.selector = selector
            self.first = self

        async def count(self):
            visible_selectors = {
                'input[name="q"]',
                "#search_icon",
                'a[href*="/images/search"]',
            }
            return 1 if self.selector in visible_selectors else 0

        async def is_visible(self):
            return True

        async def click(self):
            actions.append(("click", self.page.name, self.selector))
            if self.selector == "#search_icon":
                self.page.url = "https://www.bing.com/search?q=images"

        async def focus(self):
            pass

        async def fill(self, value):
            pass

        async def type(self, value, delay=0):
            pass

        async def press(self, key):
            pass

    class FakePage:
        def __init__(self, name, payload):
            self.name = name
            self.payload = payload
            self.url = "about:blank"

        def set_default_navigation_timeout(self, timeout):
            pass

        def set_default_timeout(self, timeout):
            pass

        def locator(self, selector):
            return FakeLocator(self, selector)

        def expect_navigation(self, **kwargs):
            return FakeNavigation()

        def expect_popup(self, **kwargs):
            popup = FakePage(
                "popup",
                {
                    "images": [{"name": "Popup Image", "url": "https://example.com/popup-image.jpg"}],
                    "totalPages": 1,
                },
            )
            popup.url = "https://www.bing.com/images/search?q=images"
            return FakePopupInfo(popup)

        async def goto(self, url, *args, **kwargs):
            actions.append(("goto", self.name, url))
            self.url = url

        async def wait_for_load_state(self, state):
            actions.append(("load_state", self.name, state))

        async def wait_for_selector(self, *args, **kwargs):
            actions.append(("wait_for_selector", self.name))

        async def evaluate(self, expression):
            actions.append(("evaluate", self.name))
            if "window.scrollTo" in expression:
                return None
            return self.payload

        async def title(self):
            return ""

    class FakeContext:
        async def new_page(self):
            return FakePage(
                "main",
                {
                    "images": [{"name": "Main Image", "url": "https://example.com/main-image.jpg"}],
                    "totalPages": 1,
                },
            )

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
    monkeypatch.setattr("browser_fetch_mcp.search.sleep_random_ms", lambda delay_range: _noop())

    service = SearchService(FakeBrowser())  # type: ignore[arg-type]
    payload = await service._evaluate_search(
        "https://cn.bing.com/images/search?q=images",
        "() => []",
        ["img.mimg"],
        engine="bing",
        keyword="images",
        image_search=True,
    )

    assert payload == {
        "images": [{"name": "Popup Image", "url": "https://example.com/popup-image.jpg"}],
        "totalPages": 1,
    }
    assert ("load_state", "popup", "domcontentloaded") in actions
    assert ("wait_for_selector", "popup") in actions
    assert ("evaluate", "popup") in actions


async def _noop() -> None:
    return None


async def test_search_returns_page_metadata(monkeypatch) -> None:
    async def fake_evaluate_search(self, url, extract_js, selectors, *, engine=None, **kwargs):
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
    assert result.rows[0].context == "preview for https://example.com"


async def test_search_can_disable_link_context(monkeypatch) -> None:
    async def fake_evaluate_search(self, url, extract_js, selectors, *, engine=None, **kwargs):
        del self, url, extract_js, selectors, engine, kwargs
        return {
            "rows": [{"title": "Result", "url": "https://example.com"}],
            "totalPages": 1,
        }

    class NoFetchBrowser(FakeBrowser):
        async def batch_fetch(self, *args, **kwargs):
            raise AssertionError("batch_fetch should not be called")

    monkeypatch.setattr(SearchService, "_evaluate_search", fake_evaluate_search)

    service = SearchService(NoFetchBrowser())  # type: ignore[arg-type]
    result = await service.search("query", engine="bing", enable_show_link_context=False)

    assert result.rows[0].context == ""


async def test_search_img_returns_image_metadata(monkeypatch) -> None:
    async def fake_evaluate_search(self, url, extract_js, selectors, *, engine=None, **kwargs):
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
