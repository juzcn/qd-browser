"""工具函数模块"""

import hashlib
import re
from urllib.parse import urlparse

import httpx


def get_stable_hash(url: str) -> str:
    """生成稳定的 URL 哈希值（跨进程一致）"""
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:16]


def clean_filename(text: str, max_length: int = 100) -> str:
    """清理文件名中的非法字符"""
    # 先移除所有空白控制字符（换行、制表符等）
    clean_text = re.sub(r"[\x00-\x1F\x7F]+", " ", text)
    # 再替换文件名非法字符
    clean_text = re.sub(r'[<>:"/\\|?*]', "_", clean_text.strip())
    # 合并多个空格
    clean_text = re.sub(r"\s+", " ", clean_text)
    return clean_text[:max_length]




async def is_download_url(url: str) -> bool:
    """判断 URL 是否是下载文件链接"""
    doc_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar"]
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in doc_extensions):
        return True

    try:
        response = httpx.head(url, follow_redirects=True, timeout=10)
        content_type = response.headers.get("content-type", "").lower()
        content_disposition = response.headers.get("content-disposition", "").lower()
        if "attachment" in content_disposition:
            return True
        if any(
            ct in content_type
            for ct in ["pdf", "msword", "document", "spreadsheet", "presentation", "octet-stream"]
        ):
            return True
    except Exception:
        pass
    return False


async def verify_domain_accessibility(domain: str) -> tuple[bool, str, str, int, bool]:
    """验证域名可访问性并获取 title

    Returns:
        (is_accessible, page_title, accessed_url, status_code, ssl_skipped)
    """
    page_title = ""

    async def _check():
        nonlocal page_title
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # 先尝试主域名
            try:
                url = f"https://{domain}"
                response = await client.get(url)
                response.raise_for_status()
                title_match = re.search(
                    r"<title[^>]*>([^<]+)</title>", response.text, re.IGNORECASE
                )
                page_title = title_match.group(1).strip() if title_match else ""
                return True, page_title, url, response.status_code, False
            except Exception:
                pass
            # 主域名失败，尝试 www 域名
            try:
                www_domain = f"www.{domain}"
                url = f"https://{www_domain}"
                response = await client.get(url)
                response.raise_for_status()
                title_match = re.search(
                    r"<title[^>]*>([^<]+)</title>", response.text, re.IGNORECASE
                )
                page_title = title_match.group(1).strip() if title_match else ""
                return True, page_title, url, response.status_code, False
            except Exception:
                pass
            # 都失败，尝试不验证 SSL
            try:
                url = f"https://{domain}"
                response = await client.get(url, verify=False)
                response.raise_for_status()
                title_match = re.search(
                    r"<title[^>]*>([^<]+)</title>", response.text, re.IGNORECASE
                )
                page_title = title_match.group(1).strip() if title_match else ""
                return True, page_title, url, response.status_code, True
            except Exception:
                return False, "", "", 0, False

    return await _check()
