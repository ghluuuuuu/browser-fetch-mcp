from __future__ import annotations

from typing import Any

from .config import Settings


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1920, "height": 945}
SCREEN = {"width": 1920, "height": 1080}
LOCALE = "zh-CN"
TIMEZONE_ID = "Asia/Shanghai"
DEVICE_SCALE_FACTOR = 2

BROWSER_FINGERPRINT_INIT_SCRIPT = """
(() => {
  const defineValue = (target, property, value) => {
    try {
      Object.defineProperty(target, property, {
        configurable: true,
        get: () => value,
      });
    } catch {
      // Some browser/runtime combinations may reject redefining native fields.
    }
  };

  defineValue(Navigator.prototype, 'platform', 'Win32');
  defineValue(Navigator.prototype, 'language', 'zh-CN');
  defineValue(Navigator.prototype, 'languages', ['zh-CN', 'zh']);
  defineValue(Navigator.prototype, 'doNotTrack', '1');
  defineValue(Navigator.prototype, 'hardwareConcurrency', 24);
  defineValue(Navigator.prototype, 'deviceMemory', 32);
  defineValue(Screen.prototype, 'width', 1920);
  defineValue(Screen.prototype, 'height', 1080);
  defineValue(Screen.prototype, 'colorDepth', 32);
  defineValue(Screen.prototype, 'pixelDepth', 32);
})();
"""


def browser_context_options(settings: Settings | None = None) -> dict[str, Any]:
    options = {
        "user_agent": USER_AGENT,
        "viewport": VIEWPORT,
        "screen": SCREEN,
        "device_scale_factor": DEVICE_SCALE_FACTOR,
        "locale": LOCALE,
        "timezone_id": TIMEZONE_ID,
        "is_mobile": False,
        "has_touch": False,
        "extra_http_headers": {
            "Accept-Language": "zh-CN,zh;q=0.9",
            "DNT": "1",
        },
    }
    if settings and settings.browser_proxy_server:
        proxy: dict[str, str] = {"server": settings.browser_proxy_server}
        if settings.browser_proxy_username:
            proxy["username"] = settings.browser_proxy_username
        if settings.browser_proxy_password:
            proxy["password"] = settings.browser_proxy_password
        options["proxy"] = proxy
    return options


async def create_browser_context(browser, settings: Settings | None = None):
    context = await browser.new_context(**browser_context_options(settings))
    await context.add_init_script(BROWSER_FINGERPRINT_INIT_SCRIPT)
    return context
