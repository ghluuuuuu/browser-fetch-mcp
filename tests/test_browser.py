from browser_fetch_mcp.browser import (
    BrowserClient,
    PAGE_ASSETS_JS,
    RenderedContentSignal,
    auto_scroll_page,
    wait_for_rendered_content,
)
from browser_fetch_mcp.config import Settings
from browser_fetch_mcp.models import make_fetch_result


class FakeProbePage:
    def __init__(self, values: list[dict]):
        self.values = values
        self.calls = 0

    async def evaluate(self, expression):
        del expression
        self.calls += 1
        if self.values:
            return self.values.pop(0)
        return {}


async def test_wait_for_rendered_content_waits_for_delayed_text() -> None:
    page = FakeProbePage(
        [
            {"textLength": 0, "links": 0, "images": 0},
            {"textLength": 12, "links": 0, "images": 0},
            {"textLength": 12, "links": 0, "images": 0},
        ]
    )

    signal = await wait_for_rendered_content(page, timeout_ms=1_000, poll_interval_ms=1)

    assert signal == RenderedContentSignal(text_length=12, links=0, images=0)
    assert page.calls == 3


async def test_wait_for_rendered_content_accepts_asset_only_pages() -> None:
    page = FakeProbePage(
        [
            {"textLength": 0, "links": 0, "images": 0},
            {"textLength": 0, "links": 1, "images": 2},
            {"textLength": 0, "links": 1, "images": 2},
        ]
    )

    signal = await wait_for_rendered_content(page, timeout_ms=1_000, poll_interval_ms=1)

    assert signal == RenderedContentSignal(text_length=0, links=1, images=2)
    assert page.calls == 3


async def test_wait_for_rendered_content_exits_when_content_never_appears() -> None:
    page = FakeProbePage(
        [
            {"textLength": 0, "links": 0, "images": 0},
            {"textLength": 0, "links": 0, "images": 0},
        ]
    )

    signal = await wait_for_rendered_content(page, timeout_ms=0, poll_interval_ms=1)

    assert signal == RenderedContentSignal()
    assert page.calls == 1


async def test_wait_for_rendered_content_requires_stability() -> None:
    page = FakeProbePage(
        [
            {"textLength": 4, "links": 0, "images": 0},
            {"textLength": 8, "links": 0, "images": 0},
            {"textLength": 8, "links": 0, "images": 0},
        ]
    )

    signal = await wait_for_rendered_content(page, timeout_ms=1_000, poll_interval_ms=1)

    assert signal == RenderedContentSignal(text_length=8, links=0, images=0)
    assert page.calls == 3


async def test_batch_fetch_uses_single_fetch_flow_for_each_url(monkeypatch) -> None:
    client = BrowserClient(Settings(batch_concurrency=1))
    calls = []

    async def fake_fetch(url: str, **kwargs):
        calls.append((url, kwargs))
        return make_fetch_result(url, f"content for {url}", kwargs["start_index"], kwargs["max_length"])

    monkeypatch.setattr(client, "fetch", fake_fetch)

    results = await client.batch_fetch(
        ["https://example.com/1", "https://example.com/2"],
        start_index=0,
        max_length=100,
        include_links=False,
        include_images=True,
        auto_scroll=True,
        auto_scroll_max_distance=1_600,
    )

    assert [call[0] for call in calls] == ["https://example.com/1", "https://example.com/2"]
    assert [result.url for result in results] == ["https://example.com/1", "https://example.com/2"]
    assert all(call[1]["max_length"] == 100 for call in calls)
    assert all(call[1]["include_links"] is False for call in calls)
    assert all(call[1]["include_images"] is True for call in calls)
    assert all(call[1]["auto_scroll"] is True for call in calls)
    assert all(call[1]["auto_scroll_max_distance"] == 1_600 for call in calls)


class FakeScrollPage:
    def __init__(self):
        self.scroll_args = None
        self.probes = [
            {"textLength": 10, "links": 0, "images": 0},
            {"textLength": 10, "links": 0, "images": 0},
        ]

    async def evaluate(self, expression, arg=None):
        if arg is not None:
            self.scroll_args = arg
            return {"distance": arg["maxDistance"], "scrollHeight": 2_000, "scrollY": arg["maxDistance"]}
        if self.probes:
            return self.probes.pop(0)
        return {"textLength": 10, "links": 0, "images": 0}


async def test_auto_scroll_page_scrolls_with_max_distance() -> None:
    page = FakeScrollPage()

    await auto_scroll_page(page, max_distance=1_600)

    assert page.scroll_args["maxDistance"] == 1_600
    assert page.scroll_args["step"] == 800


async def test_auto_scroll_page_skips_non_positive_distance() -> None:
    page = FakeScrollPage()

    await auto_scroll_page(page, max_distance=0)

    assert page.scroll_args is None


def test_page_assets_script_uses_contextual_labels_for_empty_assets() -> None:
    assert "const contextualLabel = (node) =>" in PAGE_ASSETS_JS
    assert "const labelFor = (node) => directLabel(node) || contextualLabel(node);" in PAGE_ASSETS_JS
    assert "alt: firstUsefulText([node.getAttribute('alt'), label])" in PAGE_ASSETS_JS


def test_page_assets_script_can_skip_links_and_images() -> None:
    assert "({includeLinks, includeImages}) =>" in PAGE_ASSETS_JS
    assert "const links = includeLinks ?" in PAGE_ASSETS_JS
    assert "const images = includeImages ?" in PAGE_ASSETS_JS
