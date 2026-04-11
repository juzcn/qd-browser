"""浏览器管理模块"""


from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from .config import settings


class BrowserManager:
    """浏览器管理器"""

    def __init__(self):
        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None

    async def start(self):
        """启动浏览器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=settings.headless,
            slow_mo=settings.slow_mo,
        )
        self.context = await self.browser.new_context(
            user_agent=settings.user_agent,
            accept_downloads=True,
        )

    async def stop(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def new_page(self) -> Page:
        """创建新页面"""
        if not self.context:
            await self.start()
        return await self.context.new_page()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
