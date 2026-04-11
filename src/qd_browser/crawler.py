"""爬虫核心模块"""

import asyncio
import json
from pathlib import Path
from typing import Any

from playwright.async_api import Page
from rich.console import Console

from .browser import BrowserManager
from .config import settings
from .parser import ContentParser
from .utils import clean_filename, get_stable_hash

console = Console()


class Crawler:
    """综合爬虫"""

    def __init__(self):
        self.browser_manager = BrowserManager()
        self.output_dir = Path(settings.base_output_dir)
        # 注意：settings.base_output_dir 已包含 domain
        # 注意：目录应由调用者通过 ensure_output_dir() 创建

    @property
    def browser_context(self):
        """获取浏览器上下文（用于下载 fallback）"""
        return self.browser_manager.context

    async def crawl_page(
        self,
        url: str,
        wait_selector: str | None = None,
        wait_time: float | None = None,
    ) -> dict[str, Any]:
        """爬取单个页面

        Returns:
            包含 url, title, description, main_content, markdown, metadata, attachments, raw_html 的字典
        """
        page: Page | None = None
        try:
            page = await self.browser_manager.new_page()

            console.print(f"[blue]正在访问: {url}[/blue]")
            response = await page.goto(url, wait_until="commit", timeout=settings.browser_timeout)

            if response and response.status >= 400:
                console.print(f"[yellow]HTTP {response.status} {response.status_text}[/yellow]")

            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=settings.browser_timeout)
            elif wait_time:
                await asyncio.sleep(wait_time)
            else:
                await asyncio.sleep(settings.default_wait_time)

            html = await page.content()
            current_url = page.url

            parser = ContentParser(base_url=current_url)
            main_content = parser.extract_main_content(html)
            markdown = parser.html_to_markdown(html)
            metadata = parser.parse_metadata(html)
            attachments = parser.extract_attachments(html)

            result = {
                "url": current_url,
                "title": metadata.get("title") or "",
                "description": metadata.get("description") or "",
                "main_content": main_content or "",
                "markdown": markdown,
                "metadata": metadata,
                "attachments": attachments,
                "raw_html": html if settings.save_html else None,
            }

            console.print(f"[green]爬取成功: {result['title'] or current_url}[/green]")
            return result

        except Exception as e:
            console.print(f"[red]爬取失败 {url}: {e}[/red]")
            raise
        finally:
            if page:
                await page.close()

    async def save_result(
        self, result: dict[str, Any], base_path: Path, filename: str | None = None
    ) -> Path:
        """保存爬取结果到指定目录

        Args:
            result: crawl_page 返回的结果
            base_path: 基础目录
            filename: 文件名（不含后缀）

        Returns:
            保存的文件路径（带后缀）
        """
        if not filename:
            title = clean_filename(result.get("title", "page"), max_length=50)
            if settings.hash_url:
                filename = f"{title}_{get_stable_hash(result['url'])}"
            else:
                filename = title

        if filename == "页面" or filename == "page":
            if settings.language == "zh":
                content_filename = "页面"
            else:
                content_filename = "page"
        else:
            content_filename = filename

        file_base_path = base_path / content_filename

        if settings.save_markdown and result.get("markdown"):
            md_path = file_base_path.with_suffix(".md")
            md_content = f"# {result.get('title', '')}\n\n"
            md_content += f"来源: {result['url']}\n\n"
            if result.get("description"):
                md_content += f"描述: {result['description']}\n\n"
            md_content += f"---\n\n{result['markdown']}"
            md_path.write_text(md_content, encoding="utf-8")

        if settings.save_html and result.get("raw_html"):
            html_path = file_base_path.with_suffix(".html")
            html_path.write_text(result["raw_html"], encoding="utf-8")

        if settings.debug:
            json_path = file_base_path.with_suffix(".json")
            json_data = {k: v for k, v in result.items() if k != "raw_html"}
            json_path.write_text(
                json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        if settings.save_markdown and result.get("markdown"):
            return file_base_path.with_suffix(".md")
        elif settings.save_html and result.get("raw_html"):
            return file_base_path.with_suffix(".html")
        return file_base_path

    async def crawl_and_save(
        self,
        url: str,
        custom_title: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """爬取页面并保存（不下载附件）

        Args:
            url: 要爬取的 URL
            custom_title: 自定义标题
            **kwargs: 传递给 crawl_page 的参数

        Returns:
            包含以下键的字典:
                - url: 页面 URL
                - title: 页面标题
                - cleaned_title: 清理后的标题
                - attachments: 附件列表
                - saved_path: 保存的文件路径
                - output_folder: 输出文件夹路径（如果有附件则为子文件夹）
        """
        result = await self.crawl_page(url, **kwargs)

        has_attachments = bool(result.get("attachments"))

        if custom_title:
            title = clean_filename(custom_title, max_length=50)
        else:
            title = clean_filename(result.get("title", "page"), max_length=50)
        if settings.hash_url:
            base_name = f"{title}_{get_stable_hash(result['url'])}"
        else:
            base_name = title

        saved_path: Path
        output_folder: Path

        if has_attachments:
            folder_path = self.output_dir / base_name
            folder_path.mkdir(parents=True, exist_ok=True)

            if settings.language == "zh":
                page_filename = "页面"
            else:
                page_filename = "page"
            saved_path = await self.save_result(result, folder_path, page_filename)
            output_folder = folder_path
        else:
            saved_path = await self.save_result(result, self.output_dir, base_name)
            output_folder = self.output_dir

        metadata = result.get("metadata", {})
        return {
            "url": result["url"],
            "title": result.get("title", ""),
            "cleaned_title": title,
            "attachments": result.get("attachments", []),
            "saved_path": saved_path,
            "output_folder": output_folder,
            "page_date": metadata.get("date"),
        }

    async def __aenter__(self):
        await self.browser_manager.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.browser_manager.stop()
