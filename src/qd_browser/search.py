"""搜索功能模块"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
import tldextract
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from .browser import BrowserManager


def get_api_keys(env_prefix: str) -> list[str]:
    """获取所有 API key 列表"""
    keys = []
    i = 1
    while True:
        key = os.getenv(f"{env_prefix}_{i}")
        if key:
            keys.append(key)
            i += 1
        else:
            break
    if not keys:
        key = os.getenv(env_prefix)
        if key:
            keys.append(key)
    if not keys:
        raise Exception(f"未找到 {env_prefix} 或 {env_prefix}_1 环境变量")
    return keys


async def serper_search(query: str, count: int = 10) -> list[dict[str, Any]]:
    """Serper 搜索（支持 API key fallback + 浏览器搜索备用）"""
    api_keys = get_api_keys("SERPER_API_KEY")
    url = "https://google.serper.dev/search"

    last_exception = None
    for api_key in api_keys:
        try:
            headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

            payload = {"q": query, "num": count}

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                results = response.json()

                organic = results.get("organic", [])
                datas = []
                for item in organic:
                    datas.append(
                        {
                            "url": item.get("link", ""),
                            "title": item.get("title", ""),
                            "source": "Serper",
                            "date": item.get("date", ""),
                        }
                    )

                return datas
        except Exception as e:
            last_exception = e
            continue

    # API 全部失败，使用浏览器搜索作为备用
    try:
        return await browser_google_search(query, count)
    except Exception as browser_e:
        raise Exception(f"Serper API 和浏览器 Google 搜索都失败了: {last_exception}, {browser_e}")


async def baidu_search(query: str, count: int = 10) -> list[dict[str, Any]]:
    """百度搜索（支持 API key fallback + 浏览器搜索备用）"""
    api_keys = get_api_keys("BAIDU_API_KEY")
    url = "https://qianfan.baidubce.com/v2/ai_search/web_search"

    last_exception = None
    for api_key in api_keys:
        try:
            request_body = {
                "messages": [{"content": query, "role": "user"}],
                "search_source": "baidu_search_v2",
                "resource_type_filter": [{"type": "web", "top_k": count}],
                "search_filter": {},
            }

            headers = {
                "Authorization": f"Bearer {api_key}",
                "X-Appbuilder-From": "openclaw",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=request_body, headers=headers)
                response.raise_for_status()
                results = response.json()

                if "code" in results:
                    raise Exception(results.get("message", "未知错误"))

                datas = results.get("references", [])
                for item in datas:
                    item.pop("snippet", None)
                    item["source"] = "百度"
                    date = item.get("date", "")
                    if date:
                        date = date.split(" ")[0]
                    item["date"] = date

                return datas
        except Exception as e:
            last_exception = e
            continue

    # API 全部失败，使用浏览器搜索作为备用
    try:
        return await browser_baidu_search(query, count)
    except Exception as browser_e:
        raise Exception(f"百度 API 和浏览器百度搜索都失败了: {last_exception}, {browser_e}")


def merge_results(results_list: list[list[dict]]) -> list[dict]:
    """合并去重搜索结果"""
    seen_urls = set()
    merged = []
    for results in results_list:
        for item in results:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                merged.append(item)
    return merged


def filter_by_domain(results: list[dict], target_domain: str) -> list[dict]:
    """按域名过滤搜索结果"""
    filtered = []
    for item in results:
        url = item.get("url", "")
        if not url:
            continue
        try:
            parsed = urlparse(url)
            host = parsed.netloc
            extracted = tldextract.extract(host)
            item_domain = extracted.top_domain_under_public_suffix or host
            if item_domain.lower() == target_domain.lower():
                filtered.append(item)
        except Exception:
            continue
    return filtered


def save_search_results_debug(
    output_dir: str,
    serper_results: list[dict],
    baidu_results: list[dict],
    merged_results: list[dict],
) -> Path:
    """保存搜索结果到 debug 文件"""
    debug_data = {
        "serper_results": serper_results,
        "baidu_results": baidu_results,
        "merged_results": merged_results,
    }
    debug_path = Path(output_dir) / "search_results_debug.json"
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(json.dumps(debug_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return debug_path


async def browser_baidu_search(query: str, count: int = 10) -> list[dict[str, Any]]:
    """使用浏览器进行百度搜索"""
    from rich.console import Console

    console = Console()
    console.print("[yellow]百度 API 不可用，切换到浏览器百度搜索...[/yellow]")

    async with BrowserManager() as browser_manager:
        page = await browser_manager.new_page()
        try:
            # 访问百度搜索
            search_url = f"https://www.baidu.com/s?{urlencode({'wd': query})}"
            await page.goto(search_url, timeout=60000)
            await asyncio.sleep(2)

            # 滚动页面加载更多结果
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            results = []
            # 百度搜索结果通常在 .result 或 .c-container 中
            for item in soup.select(".result, .c-container")[:count]:
                try:
                    title_elem = item.select_one("h3 a, .t a")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get("href", "")

                    # 百度的链接是重定向链接，需要跳转到真实链接
                    # 这里我们暂时保存原始链接
                    if url and title:
                        results.append(
                            {
                                "url": url,
                                "title": title,
                                "source": "百度(浏览器)",
                                "date": "",
                            }
                        )
                except Exception:
                    continue

            console.print(f"[green]浏览器百度搜索返回 {len(results)} 条结果[/green]")
            return results

        finally:
            await page.close()


async def browser_google_search(query: str, count: int = 10) -> list[dict[str, Any]]:
    """使用浏览器进行 Google 搜索"""
    from rich.console import Console

    console = Console()
    console.print("[yellow]Serper API 不可用，切换到浏览器 Google 搜索...[/yellow]")

    async with BrowserManager() as browser_manager:
        page = await browser_manager.new_page()
        try:
            # 访问 Google 搜索
            search_url = f"https://www.google.com/search?{urlencode({'q': query, 'num': count})}"
            await page.goto(search_url, timeout=60000)
            await asyncio.sleep(2)

            # 滚动页面加载更多结果
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(1)

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            results = []
            # Google 搜索结果通常在 .g 中
            for item in soup.select(".g")[:count]:
                try:
                    title_elem = item.select_one("h3")
                    link_elem = item.select_one("a")
                    if not title_elem or not link_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    url = link_elem.get("href", "")

                    # 提取日期（如果有）
                    date = ""
                    date_elem = item.select_one("span.LEwnzc, span.f")
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        # 简单的日期提取
                        if date_text:
                            date = date_text

                    if url and title and url.startswith("http"):
                        results.append(
                            {
                                "url": url,
                                "title": title,
                                "source": "Google(浏览器)",
                                "date": date,
                            }
                        )
                except Exception:
                    continue

            console.print(f"[green]浏览器 Google 搜索返回 {len(results)} 条结果[/green]")
            return results

        finally:
            await page.close()


def load_env():
    """加载 .env 文件"""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
