from browser_fetch_mcp.browser_context import (
    BROWSER_FINGERPRINT_INIT_SCRIPT,
    USER_AGENT,
    browser_context_options,
    create_browser_context,
)
from browser_fetch_mcp.config import Settings


def test_browser_context_options_match_requested_fingerprint() -> None:
    options = browser_context_options()

    assert options["user_agent"] == USER_AGENT
    assert options["viewport"] == {"width": 1920, "height": 945}
    assert options["screen"] == {"width": 1920, "height": 1080}
    assert options["device_scale_factor"] == 2
    assert options["locale"] == "zh-CN"
    assert options["timezone_id"] == "Asia/Shanghai"
    assert options["extra_http_headers"] == {
        "Accept-Language": "zh-CN,zh;q=0.9",
        "DNT": "1",
    }
    assert "proxy" not in options


def test_browser_context_options_adds_configured_proxy() -> None:
    settings = Settings(
        browser_proxy_server="socks5://127.0.0.1:1080",
        browser_proxy_username=" user ",
        browser_proxy_password=" pass ",
    )

    options = browser_context_options(settings)

    assert options["proxy"] == {
        "server": "socks5://127.0.0.1:1080",
        "username": "user",
        "password": "pass",
    }


def test_fingerprint_init_script_overrides_readonly_fields() -> None:
    assert "Navigator.prototype, 'platform', 'Win32'" in BROWSER_FINGERPRINT_INIT_SCRIPT
    assert "Navigator.prototype, 'languages', ['zh-CN', 'zh']" in BROWSER_FINGERPRINT_INIT_SCRIPT
    assert "Navigator.prototype, 'hardwareConcurrency', 24" in BROWSER_FINGERPRINT_INIT_SCRIPT
    assert "Navigator.prototype, 'deviceMemory', 32" in BROWSER_FINGERPRINT_INIT_SCRIPT
    assert "Screen.prototype, 'colorDepth', 32" in BROWSER_FINGERPRINT_INIT_SCRIPT


async def test_create_browser_context_applies_options_and_init_script() -> None:
    class FakeContext:
        def __init__(self):
            self.scripts = []

        async def add_init_script(self, script):
            self.scripts.append(script)

    class FakeBrowser:
        def __init__(self):
            self.context = FakeContext()
            self.options = None

        async def new_context(self, **kwargs):
            self.options = kwargs
            return self.context

    browser = FakeBrowser()
    context = await create_browser_context(browser)

    assert context is browser.context
    assert browser.options == browser_context_options()
    assert browser.context.scripts == [BROWSER_FINGERPRINT_INIT_SCRIPT]
