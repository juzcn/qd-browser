"""内容解析模块"""

from typing import Any
from urllib.parse import urljoin, urlparse

import trafilatura
from bs4 import BeautifulSoup


class ContentParser:
    """内容解析器"""

    def __init__(self, base_url: str = ""):
        self.base_url = base_url

    def extract_main_content(self, html: str) -> str | None:
        """提取网页正文内容（纯文本）"""
        return trafilatura.extract(html, include_links=True, include_images=True)

    def html_to_markdown(self, html: str) -> str:
        """HTML 转换为 Markdown（使用 trafilatura 纯净输出）"""
        markdown = trafilatura.extract(
            html,
            output_format="markdown",
            include_links=True,
            include_images=True,
            include_tables=True,
        )
        return markdown or ""

    def parse_metadata(self, html: str) -> dict[str, Any]:
        """解析网页元数据"""
        soup = BeautifulSoup(html, "lxml")

        metadata = {
            "title": None,
            "description": None,
            "author": None,
            "date": None,
            "links": [],
            "images": [],
        }

        # 标题
        if soup.title:
            metadata["title"] = soup.title.string

        # meta 标签
        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            prop = meta.get("property", "").lower()
            content = meta.get("content", "")

            if name == "description" or prop == "og:description":
                metadata["description"] = content
            elif name == "author":
                metadata["author"] = content

        # 发布日期
        date_elem = soup.find("time")
        if date_elem:
            metadata["date"] = date_elem.get("datetime") or date_elem.get_text()

        # 链接
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if self.base_url:
                href = urljoin(self.base_url, href)
            text = a.get_text(strip=True)
            metadata["links"].append({"url": href, "text": text})

        # 图片
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if self.base_url:
                src = urljoin(self.base_url, src)
            alt = img.get("alt", "")
            metadata["images"].append({"url": src, "alt": alt})

        return metadata

    def extract_attachments(self, html: str) -> list[dict]:
        """提取附件链接（PDF、Word、Excel 等）"""
        soup = BeautifulSoup(html, "lxml")
        attachments = []

        doc_extensions = [
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".zip",
            ".rar",
        ]

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if self.base_url:
                href = urljoin(self.base_url, href)

            parsed = urlparse(href)
            path_lower = parsed.path.lower()

            if any(path_lower.endswith(ext) for ext in doc_extensions):
                text = a.get_text(strip=True)
                attachments.append({"url": href, "text": text})

        return attachments
