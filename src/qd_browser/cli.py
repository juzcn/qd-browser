"""CLI 命令行入口"""

import asyncio
from pathlib import Path
from typing import Any

import tldextract
import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import settings
from .crawler import Crawler
from .downloader import Downloader
from .history import get_history, get_user_config_dir
from .search import (
    baidu_search,
    filter_by_domain,
    load_env,
    merge_results,
    save_search_results_debug,
    serper_search,
)
from .utils import clean_filename, is_download_url, verify_domain_accessibility


def ensure_output_dir(dir_path: str | Path) -> Path:
    """确保输出目录存在（不记录到 created_dirs）

    Args:
        dir_path: 目录路径

    Returns:
        解析后的目录路径
    """
    path = Path(dir_path).resolve()
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return path


async def download_file_only(
    url: str,
    url_title: str | None = None,
    browser_context: Any = None,
) -> Path:
    """直接下载文件

    注意：调用前需确保全局 settings 已设置好

    Args:
        url: 要下载的文件 URL
        url_title: URL 的标题/描述
        browser_context: Playwright 浏览器上下文（用于 403 fallback）
    """
    base_dir = Path(settings.base_output_dir)
    base_dir = ensure_output_dir(base_dir)

    async with Downloader(
        download_dir=str(base_dir),
        browser_context=browser_context,
    ) as downloader:
        filepath = await downloader.download(url, link_text=url_title)
        console.print()
        console.print(f"[green]文件已保存: {filepath}[/green]")
        return filepath


async def process_single_url(
    url: str,
    url_title: str | None = None,
    skip_visited: bool = True,
    domain: str | None = None,
    search_date: str | None = None,
) -> dict[str, Any] | None:
    """处理单个 URL：判断是文件还是网页，相应地下载或爬取

    注意：如果传入 domain 参数，会临时覆盖 settings.domain
    """
    history = get_history()

    # 保存原始 domain，临时覆盖
    original_domain = settings.domain
    if domain is not None:
        settings.domain = domain

    try:
        # 确保输出目录存在
        base_dir = Path(settings.base_output_dir)
        base_dir = ensure_output_dir(base_dir)

        # 检查是否已访问过（只跳过成功状态的，失败的可以重试）
        if skip_visited and history.has_url(url):
            entry = history.get_entry(url)
            if entry and entry.status == "success":
                console.print(f"[yellow]跳过已访问 URL ({entry.status}): {url}[/yellow]")
                return None

        # 先创建 Crawler（获取 browser_context 用于下载 fallback）
        async with Crawler() as crawler:
            # 判断是否是下载文件
            if await is_download_url(url):
                console.print("[blue]检测到文件链接[/blue]")
                filepath = await download_file_only(
                    url,
                    url_title=url_title,
                    browser_context=crawler.browser_context,
                )
                cleaned_title = clean_filename(url_title) if url_title else None
                history.mark_success(url, title=cleaned_title, local_path=filepath)
                return None

            # 否则按网页爬取
            result = await crawler.crawl_and_save(url, custom_title=url_title)
            # 显示结果摘要
            console.print()
            table = Table(title="爬取结果")
            table.add_column("项目", style="cyan")
            table.add_column("内容", style="green")
            table.add_row("标题", result.get("title", "")[:80])
            table.add_row("URL", result.get("url", ""))
            table.add_row("附件数量", str(len(result.get("attachments", []))))
            console.print(table)

            # 下载附件
            attachments = result.get("attachments", [])
            if attachments:
                console.print(f"[blue]开始下载 {len(attachments)} 个附件...[/blue]")
                output_folder = result["output_folder"]
                async with Downloader(
                    download_dir=str(output_folder / Path(settings.download_dir).name),
                    browser_context=crawler.browser_context,
                ) as downloader:
                    for attachment in attachments:
                        att_url = attachment.get("url", "")
                        att_text = attachment.get("text", "")
                        cleaned_title = clean_filename(att_text) if att_text else None
                        try:
                            filepath = await downloader.download(att_url, link_text=att_text)
                            history.mark_success(att_url, title=cleaned_title, local_path=filepath)
                        except Exception as e:
                            history.mark_failed(att_url, error=str(e), title=cleaned_title)

            # 记录成功（优先用网页时间，没有则用搜索引擎时间）
            saved_path = result.get("saved_path")
            cleaned_title = result.get("cleaned_title")
            page_date = result.get("page_date") or search_date
            history.mark_success(url, title=cleaned_title, local_path=saved_path, page_date=page_date)
            return result
    except Exception as e:
        cleaned_title = clean_filename(url_title) if url_title else None
        history.mark_failed(url, error=str(e), title=cleaned_title)
        raise
    finally:
        # 恢复原始 domain
        settings.domain = original_domain


app = typer.Typer(
    name="qd-browser",
    help="基于 Playwright 的综合爬虫 CLI 工具",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"qd-browser 版本: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """全局配置"""


@app.command(name="url-download")
def url_download(
    url: str = typer.Argument(..., help="要爬取的网页 URL"),
    output_dir: str = typer.Option("./output", help="输出目录（包含爬取结果和附件）"),
    language: str = typer.Option(
        "zh", "--language", help="语言：zh（中文）或 en（英文），影响文件夹命名"
    ),
    hash_url: bool = typer.Option(
        False, "--hash-url", help="使用稳定的 URL 哈希（MD5）作为文件名后缀"
    ),
    debug: bool = typer.Option(False, "--debug", help="调试模式：保存原始 HTML"),
    url_title: str | None = typer.Option(
        None, "--url-title", help="URL 的标题/描述，用于文件命名"
    ),
    not_skip: bool = typer.Option(False, "--not-skip", help="不跳过已访问的 URL（强制重新处理）"),
):
    """爬取单个网页并下载内容（包含附件）"""
    settings.output_dir = output_dir
    settings.language = language
    settings.hash_url = hash_url
    if debug:
        settings.debug = debug

    # 从 URL 解析域名作为 domain
    import tldextract

    extracted = tldextract.extract(url)
    domain = extracted.top_domain_under_public_suffix
    if domain:
        console.print(f"[blue]使用域名作为子目录: {domain}[/blue]")

    # 先创建并记录最顶层的 output-dir
    history = get_history()
    output_path = Path(output_dir).resolve()
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        history.add_created_dir(output_path)

    async def _process():
        await process_single_url(
            url,
            url_title=url_title,
            skip_visited=not not_skip,
            domain=domain,
            search_date=None,
        )

    try:
        asyncio.run(_process())
    except Exception as e:
        if settings.debug:
            console.print_exception()
        else:
            console.print(f"[red]错误: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="domain-download")
def domain_download(
    input_value: str = typer.Argument(..., help="域名或 URL"),
    query: str = typer.Argument(..., help="搜索关键词"),
    output_dir: str = typer.Option("./output", help="输出目录（包含爬取结果和附件）"),
    language: str = typer.Option(
        "zh", "--language", help="语言：zh（中文）或 en（英文），影响文件夹命名"
    ),
    hash_url: bool = typer.Option(
        False, "--hash-url", help="使用稳定的 URL 哈希（MD5）作为文件名后缀"
    ),
    debug: bool = typer.Option(False, "--debug", help="调试模式：保存原始 HTML"),
    not_skip: bool = typer.Option(False, "--not-skip", help="不跳过已访问的 URL（强制重新处理）"),
):
    """批量爬取多个网页（包含附件）"""
    settings.output_dir = output_dir
    settings.language = language
    settings.hash_url = hash_url
    if debug:
        settings.debug = debug

    # 先创建并记录最顶层的 output-dir
    history = get_history()
    output_path = Path(output_dir).resolve()
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        history.add_created_dir(output_path)

    # 加载 .env 文件
    load_env()

    # 第一步：用 tldextract 解析 domain-name
    extracted = tldextract.extract(input_value)
    domain = extracted.top_domain_under_public_suffix or input_value
    console.print(f"[blue]解析域名: {domain}[/blue]")

    # 第二步：验证域名的可访问性并获取 title
    console.print("[blue]验证域名可访问性...[/blue]")
    page_title = ""
    try:
        is_accessible, page_title, accessed_url, status_code, ssl_skipped = asyncio.run(
            verify_domain_accessibility(domain)
        )
        if is_accessible:
            if ssl_skipped:
                if page_title:
                    console.print(
                        f"[yellow]域名可访问（跳过 SSL 验证）: {accessed_url} (HTTP {status_code}) - {page_title}[/yellow]"
                    )
                else:
                    console.print(
                        f"[yellow]域名可访问（跳过 SSL 验证）: {accessed_url} (HTTP {status_code})[/yellow]"
                    )
            else:
                if page_title:
                    console.print(
                        f"[green]域名可访问: {accessed_url} (HTTP {status_code}) - {page_title}[/green]"
                    )
                else:
                    console.print(f"[green]域名可访问: {accessed_url} (HTTP {status_code})[/green]")
    except Exception as e:
        console.print(f"[yellow]警告: 域名访问验证失败: {e}[/yellow]")

    # 第三步：搜索
    console.print()
    console.print("[blue]========== 搜索 ==========[/blue]")
    search_query = f"{query} site:{domain}"
    console.print(f"搜索关键词: {search_query}")

    # 搜索：Serper 主搜索 + 百度补全
    serper_results = []
    baidu_results = []

    # Serper 搜索（主）
    try:
        console.print("[blue]正在使用 Serper 搜索...[/blue]")

        async def _search_serper():
            return await serper_search(search_query, count=10)

        serper_results = asyncio.run(_search_serper())
        console.print(f"[green]Serper 搜索返回 {len(serper_results)} 条结果[/green]")
    except Exception as e:
        console.print(f"[yellow]Serper 搜索失败: {e}[/yellow]")

    # 百度搜索（补全）
    try:
        console.print("[blue]正在使用百度搜索...[/blue]")

        async def _search_baidu():
            return await baidu_search(search_query, count=10)

        baidu_results = asyncio.run(_search_baidu())
        console.print(f"[green]百度搜索返回 {len(baidu_results)} 条结果[/green]")
    except Exception as e:
        console.print(f"[yellow]百度搜索失败: {e}[/yellow]")

    # 合并去重
    all_results = merge_results([serper_results, baidu_results])
    console.print(f"[green]合并后共 {len(all_results)} 条结果[/green]")

    # Debug 模式：保存搜索结果到文件
    if settings.debug:
        debug_path = save_search_results_debug(
            settings.output_dir, serper_results, baidu_results, all_results
        )
        console.print(f"[blue]Debug: 搜索结果已保存到 {debug_path}[/blue]")

    # 按域名过滤
    filtered = filter_by_domain(all_results, domain)
    console.print(f"[green]过滤后共 {len(filtered)} 条 {domain} 的结果[/green]")

    if not filtered:
        console.print("[yellow]未找到相关结果[/yellow]")
        return

    # 显示搜索结果
    console.print()
    for i, item in enumerate(filtered[:20], 1):
        console.print(
            f"[cyan]{i}.[/cyan] [yellow]{item.get('source', '')}[/yellow] [magenta]{item.get('date', '')}[/magenta]"
        )
        console.print(f"    [green]{item.get('title', '')}[/green]")
        console.print(f"    [blue]{item.get('url', '')}[/blue]")
        console.print()
    if len(filtered) > 20:
        console.print(f"... 还有 {len(filtered) - 20} 条")

    # 逐个处理 URL
    console.print()
    console.print("[blue]========== 开始处理 ==========[/blue]")
    console.print(f"共 {len(filtered)} 个链接待处理")

    async def _process_all():
        success_count = 0
        fail_count = 0
        skipped_count = 0

        history = get_history()
        for i, item in enumerate(filtered, 1):
            url = item.get("url", "")
            if not url:
                continue

            # 检查是否跳过（默认跳过成功状态的，除非 --not-skip）
            if not not_skip and history.has_url(url):
                entry = history.get_entry(url)
                if entry and entry.status == "success":
                    console.print(
                        f"[yellow][{i}/{len(filtered)}] 跳过已访问 ({entry.status}): {url}[/yellow]"
                    )
                    skipped_count += 1
                    continue

            console.print()
            console.print(f"[blue][{i}/{len(filtered)}] 处理: {url}[/blue]")

            try:
                await process_single_url(
                    url,
                    url_title=item.get("title", ""),
                    skip_visited=False,  # 这里已经检查过了
                    domain=domain,
                    search_date=item.get("date"),
                )
                success_count += 1
            except Exception as e:
                console.print(f"[red]处理失败: {e}[/red]")
                fail_count += 1

        # 显示统计
        console.print()
        table = Table(title="处理统计")
        table.add_column("项目", style="cyan")
        table.add_column("数量", style="green")
        table.add_row("总计", str(len(filtered)))
        if skipped_count > 0:
            table.add_row("跳过", str(skipped_count), style="yellow")
        table.add_row("成功", str(success_count))
        table.add_row("失败", str(fail_count))
        console.print(table)

    try:
        asyncio.run(_process_all())
    except Exception as e:
        if settings.debug:
            console.print_exception()
        else:
            console.print(f"[red]错误: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="web-download")
def web_download(
    query: str = typer.Argument(..., help="搜索关键词"),
    output_dir: str = typer.Option("./output", help="输出目录（包含爬取结果和附件）"),
    language: str = typer.Option(
        "zh", "--language", help="语言：zh（中文）或 en（英文），影响文件夹命名"
    ),
    hash_url: bool = typer.Option(
        False, "--hash-url", help="使用稳定的 URL 哈希（MD5）作为文件名后缀"
    ),
    debug: bool = typer.Option(False, "--debug", help="调试模式：保存原始 HTML"),
    not_skip: bool = typer.Option(False, "--not-skip", help="不跳过已访问的 URL（强制重新处理）"),
):
    """全网搜索并批量爬取多个网页（包含附件）"""
    settings.output_dir = output_dir
    settings.language = language
    settings.hash_url = hash_url
    if debug:
        settings.debug = debug

    # 先创建并记录最顶层的 output-dir
    history = get_history()
    output_path = Path(output_dir).resolve()
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        history.add_created_dir(output_path)

    # 加载 .env 文件
    load_env()

    # 搜索：全网搜索（不加 site: 限制）
    console.print()
    console.print("[blue]========== 搜索 ==========[/blue]")
    search_query = query
    console.print(f"搜索关键词: {search_query}")

    # 搜索：Serper 主搜索 + 百度补全
    serper_results = []
    baidu_results = []

    # Serper 搜索（主）
    try:
        console.print("[blue]正在使用 Serper 搜索...[/blue]")

        async def _search_serper():
            return await serper_search(search_query, count=10)

        serper_results = asyncio.run(_search_serper())
        console.print(f"[green]Serper 搜索返回 {len(serper_results)} 条结果[/green]")
    except Exception as e:
        console.print(f"[yellow]Serper 搜索失败: {e}[/yellow]")

    # 百度搜索（补全）
    try:
        console.print("[blue]正在使用百度搜索...[/blue]")

        async def _search_baidu():
            return await baidu_search(search_query, count=10)

        baidu_results = asyncio.run(_search_baidu())
        console.print(f"[green]百度搜索返回 {len(baidu_results)} 条结果[/green]")
    except Exception as e:
        console.print(f"[yellow]百度搜索失败: {e}[/yellow]")

    # 合并去重
    all_results = merge_results([serper_results, baidu_results])
    console.print(f"[green]合并后共 {len(all_results)} 条结果[/green]")

    # Debug 模式：保存搜索结果到文件
    if settings.debug:
        debug_path = save_search_results_debug(
            settings.output_dir, serper_results, baidu_results, all_results
        )
        console.print(f"[blue]Debug: 搜索结果已保存到 {debug_path}[/blue]")

    filtered = all_results

    if not filtered:
        console.print("[yellow]未找到相关结果[/yellow]")
        return

    # 显示搜索结果
    console.print()
    for i, item in enumerate(filtered[:20], 1):
        console.print(
            f"[cyan]{i}.[/cyan] [yellow]{item.get('source', '')}[/yellow] [magenta]{item.get('date', '')}[/magenta]"
        )
        console.print(f"    [green]{item.get('title', '')}[/green]")
        console.print(f"    [blue]{item.get('url', '')}[/blue]")
        console.print()
    if len(filtered) > 20:
        console.print(f"... 还有 {len(filtered) - 20} 条")

    # 逐个处理 URL
    console.print()
    console.print("[blue]========== 开始处理 ==========[/blue]")
    console.print(f"共 {len(filtered)} 个链接待处理")

    async def _process_all():
        import tldextract

        success_count = 0
        fail_count = 0
        skipped_count = 0

        history = get_history()
        for i, item in enumerate(filtered, 1):
            url = item.get("url", "")
            if not url:
                continue

            # 为每个 URL 单独解析域名
            extracted = tldextract.extract(url)
            url_domain = extracted.top_domain_under_public_suffix

            # 检查是否跳过（默认跳过成功状态的，除非 --not-skip）
            if not not_skip and history.has_url(url):
                entry = history.get_entry(url)
                if entry and entry.status == "success":
                    console.print(
                        f"[yellow][{i}/{len(filtered)}] 跳过已访问 ({entry.status}): {url}[/yellow]"
                    )
                    skipped_count += 1
                    continue

            console.print()
            if url_domain:
                console.print(f"[blue][{i}/{len(filtered)}] 处理: {url} (域名: {url_domain})[/blue]")
            else:
                console.print(f"[blue][{i}/{len(filtered)}] 处理: {url}[/blue]")

            try:
                await process_single_url(
                    url,
                    url_title=item.get("title", ""),
                    skip_visited=False,  # 这里已经检查过了
                    domain=url_domain,
                    search_date=item.get("date"),
                )
                success_count += 1
            except Exception as e:
                console.print(f"[red]处理失败: {e}[/red]")
                fail_count += 1

        # 显示统计
        console.print()
        table = Table(title="处理统计")
        table.add_column("项目", style="cyan")
        table.add_column("数量", style="green")
        table.add_row("总计", str(len(filtered)))
        if skipped_count > 0:
            table.add_row("跳过", str(skipped_count), style="yellow")
        table.add_row("成功", str(success_count))
        table.add_row("失败", str(fail_count))
        console.print(table)

    try:
        asyncio.run(_process_all())
    except Exception as e:
        if settings.debug:
            console.print_exception()
        else:
            console.print(f"[red]错误: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def config(
    show_settings: bool = typer.Option(False, "--settings", "-s", help="显示当前配置和路径"),
    stats: bool = typer.Option(False, "--stats", "-t", help="显示历史记录统计"),
    show_history: bool = typer.Option(False, "--history", "-l", help="列出历史记录"),
    show_dirs: bool = typer.Option(False, "--dirs", "-d", help="列出我们创建的输出目录"),
    by_status: str | None = typer.Option(
        None, "--by-status", help="按状态过滤: success/failed/skipped"
    ),
    by_site: str | None = typer.Option(None, "--by-site", help="按域名过滤"),
    by_output_dir: str | None = typer.Option(None, "--by-output-dir", help="按输出目录过滤"),
    by_url: str | None = typer.Option(None, "--by-url", "-c", help="按 URL 过滤"),
    remove_url: str | None = typer.Option(
        None, "--remove-url", "-r", help="从历史记录中移除 URL"
    ),
    remove_site: str | None = typer.Option(
        None, "--remove-site", help="移除指定域名的所有 URL 记录"
    ),
    remove_output_dir: str | None = typer.Option(
        None, "--remove-output-dir", help="移除指定输出目录的所有 URL 记录"
    ),
    remove_created_dir: str | None = typer.Option(
        None, "--remove-created-dir", help="从创建目录记录中移除目录（不删除目录本身）"
    ),
    remove_status: str | None = typer.Option(
        None, "--remove-status", help="移除指定状态的所有 URL 记录"
    ),
    init: bool = typer.Option(False, "--init", help="删除所有创建的输出目录，并清空所有历史记录"),
):
    """配置和历史记录管理"""
    # 显示配置
    if show_settings:
        table = Table(title="qd-browser 配置")
        table.add_column("配置项", style="cyan")
        table.add_column("值", style="green")
        for key, value in settings.model_dump().items():
            table.add_row(key, str(value))
        console.print(table)
        console.print()
        config_dir = get_user_config_dir()
        history_path = config_dir / "visited.json"
        console.print(f"配置目录: [cyan]{config_dir}[/cyan]")
        console.print(f"历史记录: [cyan]{history_path}[/cyan]")
        return

    history = get_history()

    # 列出创建的目录
    if show_dirs:
        created_dirs = history.get_created_dirs()
        if not created_dirs:
            console.print("[yellow]暂无创建的目录记录[/yellow]")
            return
        table = Table(title="创建的输出目录")
        table.add_column("#", style="cyan")
        table.add_column("目录路径", style="green")
        for i, dir_path in enumerate(created_dirs, 1):
            table.add_row(str(i), str(dir_path))
        console.print(table)
        return

    # 统计
    if stats:
        stats_data = history.get_stats()
        table = Table(title="访问历史统计")
        table.add_column("项目", style="cyan")
        table.add_column("数量", style="green")
        table.add_row("总计", str(stats_data["total"]))
        table.add_row("成功", str(stats_data["success"]))
        table.add_row("失败", str(stats_data["failed"]))
        table.add_row("跳过", str(stats_data["skipped"]))
        console.print(table)
        return

    # 列出历史记录
    if show_history:
        all_urls = history.get_all_urls()
        if not all_urls:
            console.print("[yellow]暂无历史记录[/yellow]")
            return
        # 应用过滤条件
        from pathlib import Path
        from urllib.parse import urlparse

        import tldextract

        filtered = dict(all_urls)

        # 按状态过滤
        if by_status:
            filtered = {url: entry for url, entry in filtered.items() if entry.status == by_status}

        # 按域名过滤
        if by_site:
            site_filtered = {}
            for url, entry in filtered.items():
                try:
                    parsed = urlparse(url)
                    host = parsed.netloc
                    extracted = tldextract.extract(host)
                    url_domain = extracted.top_domain_under_public_suffix or host
                    if url_domain.lower() == by_site.lower():
                        site_filtered[url] = entry
                except Exception:
                    continue
            filtered = site_filtered

        # 按输出目录过滤
        if by_output_dir:
            output_filtered = {}
            target_path = str(Path(by_output_dir).resolve())
            for url, entry in filtered.items():
                entry_path = entry.local_path
                if entry_path:
                    try:
                        entry_path_resolved = str(Path(entry_path).resolve())
                        if entry_path_resolved.startswith(target_path):
                            output_filtered[url] = entry
                    except Exception:
                        continue
            filtered = output_filtered

        # 按 URL 过滤
        if by_url:
            filtered = {url: entry for url, entry in filtered.items() if by_url in url}

        # 按时间倒序排列（最新的在前）
        sorted_items = sorted(filtered.items(), key=lambda x: x[1].visited_at, reverse=True)
        table = Table(title="访问历史")
        table.add_column("#", style="cyan")
        table.add_column("URL", style="blue")
        table.add_column("标题", style="green")
        table.add_column("状态", style="yellow")
        table.add_column("本地地址", style="magenta")
        for i, (url, entry) in enumerate(sorted_items, 1):
            status_style = {
                "success": "green",
                "failed": "red",
                "skipped": "yellow",
            }.get(entry.status, "white")
            table.add_row(
                str(i),
                url,
                entry.title or "",
                f"[{status_style}]{entry.status}[/{status_style}]",
                str(entry.local_path) if entry.local_path else "",
            )
        console.print(table)
        return

    # 移除 URL
    if remove_url is not None:
        if history.remove_url(remove_url):
            console.print(f"[green]已移除: {remove_url}[/green]")
        else:
            console.print(f"[yellow]URL 不在历史记录中: {remove_url}[/yellow]")
        return

    # 移除指定域名的所有 URL
    if remove_site is not None:
        confirm = typer.confirm(f"确定要移除域名 {remove_site} 的所有历史记录吗？")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            return
        count = history.remove_by_domain(remove_site)
        if count > 0:
            console.print(f"[green]已移除 {count} 条 {remove_site} 的记录[/green]")
        else:
            console.print(f"[yellow]未找到 {remove_site} 的记录[/yellow]")
        return

    # 移除指定输出目录的所有 URL
    if remove_output_dir is not None:
        confirm = typer.confirm(f"确定要移除输出目录 {remove_output_dir} 的所有历史记录吗？")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            return
        count = history.remove_by_output_dir(remove_output_dir)
        if count > 0:
            console.print(f"[green]已移除 {count} 条 {remove_output_dir} 的记录[/green]")
        else:
            console.print(f"[yellow]未找到 {remove_output_dir} 的记录[/yellow]")
        return

    # 移除指定状态的所有 URL
    if remove_status is not None:
        confirm = typer.confirm(f"确定要移除状态为 {remove_status} 的所有历史记录吗？")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            return
        count = history.remove_by_status(remove_status)
        if count > 0:
            console.print(f"[green]已移除 {count} 条 {remove_status} 的记录[/green]")
        else:
            console.print(f"[yellow]未找到 {remove_status} 的记录[/yellow]")
        return

    # 移除创建的目录记录（不删除目录本身）
    if remove_created_dir is not None:
        if history.remove_created_dir(remove_created_dir):
            console.print(f"[green]已从创建目录记录中移除: {remove_created_dir}[/green]")
        else:
            console.print(f"[yellow]目录不在创建记录中: {remove_created_dir}[/yellow]")
        return

    # 清空历史记录并删除创建的目录
    if init:
        confirm = typer.confirm("确定要删除所有创建的输出目录，并清空所有历史记录吗？")
        if not confirm:
            console.print("[yellow]已取消[/yellow]")
            return
        # 先删除所有创建的目录
        import shutil
        created_dirs = history.get_created_dirs()
        deleted_count = 0
        for dir_path in created_dirs:
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                    console.print(f"[green]已删除目录: {dir_path}[/green]")
                    deleted_count += 1
            except Exception as e:
                console.print(f"[red]删除目录失败 {dir_path}: {e}[/red]")
        # 再清空历史记录
        history.clear()
        if deleted_count > 0:
            console.print(f"[green]已删除 {deleted_count} 个目录，历史记录已清空[/green]")
        else:
            console.print("[green]历史记录已清空[/green]")
        return

    # 默认显示帮助
    console.print("请使用以下选项之一：")
    console.print("  --settings, -s              显示当前配置和路径")
    console.print("  --stats, -t                 显示历史记录统计")
    console.print("  --history, -l               列出历史记录")
    console.print("  --dirs, -d                  列出我们创建的输出目录")
    console.print("  --by-status STATUS          按状态过滤（配合 --history 使用）")
    console.print("  --by-site DOMAIN            按域名过滤（配合 --history 使用）")
    console.print("  --by-output-dir PATH        按输出目录过滤（配合 --history 使用）")
    console.print("  --by-url URL                按 URL 过滤（配合 --history 使用）")
    console.print("  --remove-url URL            从历史记录中移除 URL")
    console.print("  --remove-site DOMAIN        移除指定域名的所有记录")
    console.print("  --remove-output-dir PATH    移除指定输出目录的所有记录")
    console.print("  --remove-created-dir PATH   从创建目录记录中移除目录（不删除目录本身）")
    console.print("  --remove-status STATUS      移除指定状态的所有记录")
    console.print("  --init                      删除所有创建的输出目录，并清空所有历史记录")


if __name__ == "__main__":
    app()
