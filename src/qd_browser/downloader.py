"""下载器模块"""

import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.async_api import BrowserContext
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .config import settings
from .utils import clean_filename

console = Console()


class Downloader:
    """文件下载器"""

    def __init__(
        self,
        download_dir: str | None = None,
        browser_context: BrowserContext | None = None,
    ):
        self.download_dir = Path(download_dir or settings.download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.client: httpx.AsyncClient | None = None
        self.browser_context = browser_context

    async def __aenter__(self):
        # 使用浏览器 headers 避免 403
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=60.0,
            headers=headers,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def get_filename_from_url(self, url: str) -> str:
        """从 URL 中提取文件名"""
        parsed = urlparse(url)
        path = parsed.path
        filename = os.path.basename(path)
        if not filename:
            filename = f"download_{abs(hash(url))}.bin"
        return filename

    async def download_with_playwright(
        self, url: str, filename: str
    ) -> Path:
        """使用 Playwright 下载文件（fallback）"""
        if not self.browser_context:
            raise Exception("No browser_context available for Playwright download")

        console.print("[yellow]尝试用浏览器下载...[/yellow]")

        page = await self.browser_context.new_page()
        try:
            # 先导航到主页，建立 session
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            try:
                await page.goto(base_url, wait_until="commit", timeout=30000)
            except Exception:
                # 即使 base_url 导航失败也继续尝试下载
                pass

            # 使用 wait_for_download 模式，不设置 wait_until（直接下载）
            async with page.expect_download(timeout=60000) as download_info:
                await page.goto(url, timeout=60000)
            download = await download_info.value

            # 保存下载的文件
            download_path = self.download_dir / filename
            await download.save_as(download_path)

            console.print(f"[green]浏览器下载完成: {filename}[/green]")
            return download_path
        finally:
            await page.close()

    async def download(
        self, url: str, filename: str | None = None, link_text: str | None = None
    ) -> Path:
        """下载单个文件"""
        if filename is None:
            if link_text and link_text.strip():
                # 使用链接文字作为文件名，保留原始扩展名
                parsed = urlparse(url)
                path = parsed.path
                orig_filename = os.path.basename(path)
                _, ext = os.path.splitext(orig_filename)
                if not ext:
                    ext = ""
                # 清理链接文字中的非法字符
                clean_text = clean_filename(link_text.strip(), max_length=100)
                filename = f"{clean_text}{ext}" if clean_text else self.get_filename_from_url(url)
            else:
                filename = self.get_filename_from_url(url)

        filepath = self.download_dir / filename

        if filepath.exists():
            console.print(f"[yellow]文件已存在，跳过: {filename}[/yellow]")
            return filepath

        # 先用 httpx 尝试下载
        if self.client:
            try:
                return await self._download_with_httpx(url, filepath, filename)
            except Exception as e:
                console.print(f"[yellow]HTTP 下载失败: {e}[/yellow]")
                # 如果有 browser_context，尝试用 Playwright fallback
                if self.browser_context:
                    try:
                        return await self.download_with_playwright(url, filename)
                    except Exception as pw_e:
                        console.print(f"[yellow]浏览器下载也失败: {pw_e}[/yellow]")
                raise
        else:
            # 如果没有 client，直接尝试用 Playwright
            if self.browser_context:
                return await self.download_with_playwright(url, filename)
            raise Exception("No download method available (need httpx client or browser_context)")

    async def _download_with_httpx(
        self, url: str, filepath: Path, filename: str
    ) -> Path:
        """用 httpx 下载文件"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"下载 {filename}", total=None)

            async with self.client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                progress.update(task, total=total)

                with open(filepath, "wb") as f:
                    downloaded = 0
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress.update(task, completed=downloaded)

        console.print(f"[green]下载完成: {filename}[/green]")
        return filepath

    async def download_many(
        self, urls: list[str], max_concurrent: int | None = None
    ) -> list[Path]:
        """批量下载文件"""
        max_concurrent = max_concurrent or settings.max_concurrent_downloads
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_with_semaphore(url: str) -> Path | None:
            async with semaphore:
                try:
                    return await self.download(url)
                except Exception:
                    return None

        tasks = [download_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def download_many_with_names(
        self, attachments: list[dict], max_concurrent: int | None = None
    ) -> list[Path]:
        """批量下载文件，使用链接文字作为文件名"""
        max_concurrent = max_concurrent or settings.max_concurrent_downloads
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_with_semaphore(attachment: dict) -> Path | None:
            async with semaphore:
                try:
                    return await self.download(
                        attachment["url"], link_text=attachment.get("text", "")
                    )
                except Exception:
                    return None

        tasks = [download_with_semaphore(att) for att in attachments]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]
