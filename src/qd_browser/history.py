"""URL 访问历史管理模块"""

import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class VisitedEntry:
    """单个 URL 的访问记录"""

    visited_at: str
    title: str | None = None
    status: str = "success"  # success / failed / skipped
    local_path: str | None = None
    error: str | None = None
    page_date: str | None = None  # 页面发布/更新时间
    downloaded_at: str | None = None  # 下载完成时间


class URLHistory:
    """URL 访问历史管理器"""

    def __init__(self, history_path: Path):
        self.history_path = history_path
        self._data: dict[str, Any] | None = None

    def _ensure_loaded(self):
        """确保数据已加载"""
        if self._data is None:
            self.load()

    def load(self):
        """从文件加载历史数据"""
        if self.history_path.exists():
            with open(self.history_path, encoding="utf-8") as f:
                self._data = json.load(f)
            # 兼容旧版本，确保 created_dirs 存在
            if "created_dirs" not in self._data:
                self._data["created_dirs"] = []
        else:
            # 初始化新文件
            now = self._now_iso()
            self._data = {
                "version": "1.0",
                "created_at": now,
                "updated_at": now,
                "urls": {},
                "created_dirs": [],
            }

    def save(self):
        """保存历史数据到文件"""
        self._ensure_loaded()
        self._data["updated_at"] = self._now_iso()
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _now_iso(self) -> str:
        """获取当前时间的 ISO 格式"""
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def has_url(self, url: str) -> bool:
        """检查 URL 是否已访问过"""
        self._ensure_loaded()
        return url in self._data["urls"]

    def get_entry(self, url: str) -> VisitedEntry | None:
        """获取 URL 的访问记录"""
        self._ensure_loaded()
        entry_data = self._data["urls"].get(url)
        if entry_data:
            return VisitedEntry(**entry_data)
        return None

    def add_url(
        self,
        url: str,
        title: str | None = None,
        status: str = "success",
        local_path: Path | None = None,
        error: str | None = None,
        page_date: str | None = None,
    ):
        """添加或更新 URL 访问记录（总是覆盖，只保留最后一次）"""
        self._ensure_loaded()
        entry = VisitedEntry(
            visited_at=self._now_iso(),
            title=title,
            status=status,
            local_path=str(local_path) if local_path else None,
            error=error,
            page_date=page_date,
            downloaded_at=self._now_iso() if status == "success" else None,
        )
        self._data["urls"][url] = asdict(entry)
        self.save()

    def mark_success(
        self,
        url: str,
        title: str | None = None,
        local_path: Path | None = None,
        page_date: str | None = None,
    ):
        """标记 URL 处理成功"""
        self.add_url(url, title=title, status="success", local_path=local_path, page_date=page_date)

    def mark_failed(
        self,
        url: str,
        error: str,
        title: str | None = None,
    ):
        """标记 URL 处理失败"""
        self.add_url(url, title=title, status="failed", error=error)

    def mark_skipped(
        self,
        url: str,
        reason: str | None = None,
    ):
        """标记 URL 跳过"""
        self.add_url(url, status="skipped", error=reason)

    def remove_url(self, url: str) -> bool:
        """移除 URL 记录，返回是否成功移除"""
        self._ensure_loaded()
        if url in self._data["urls"]:
            del self._data["urls"][url]
            self.save()
            return True
        return False

    def remove_by_domain(self, domain: str) -> int:
        """移除指定域名的所有 URL 记录，返回移除的数量"""
        from urllib.parse import urlparse

        import tldextract

        self._ensure_loaded()
        removed_count = 0
        urls_to_remove = []

        for url in self._data["urls"].keys():
            try:
                parsed = urlparse(url)
                host = parsed.netloc
                extracted = tldextract.extract(host)
                url_domain = extracted.top_domain_under_public_suffix or host
                if url_domain.lower() == domain.lower():
                    urls_to_remove.append(url)
            except Exception:
                continue

        for url in urls_to_remove:
            del self._data["urls"][url]
            removed_count += 1

        if removed_count > 0:
            self.save()
        return removed_count

    def remove_by_output_dir(self, output_dir: str) -> int:
        """移除指定输出目录的所有 URL 记录，返回移除的数量"""
        from pathlib import Path

        self._ensure_loaded()
        removed_count = 0
        urls_to_remove = []
        target_path = str(Path(output_dir).resolve())

        for url, entry in self._data["urls"].items():
            entry_path = entry.get("local_path")
            if entry_path:
                try:
                    entry_path_resolved = str(Path(entry_path).resolve())
                    if entry_path_resolved.startswith(target_path):
                        urls_to_remove.append(url)
                except Exception:
                    continue

        for url in urls_to_remove:
            del self._data["urls"][url]
            removed_count += 1

        if removed_count > 0:
            self.save()
        return removed_count

    def remove_by_status(self, status: str) -> int:
        """移除指定状态的所有 URL 记录，返回移除的数量"""
        self._ensure_loaded()
        removed_count = 0
        urls_to_remove = []

        for url, entry in self._data["urls"].items():
            if entry.get("status") == status:
                urls_to_remove.append(url)

        for url in urls_to_remove:
            del self._data["urls"][url]
            removed_count += 1

        if removed_count > 0:
            self.save()
        return removed_count

    def get_all_urls(self) -> dict[str, VisitedEntry]:
        """获取所有 URL 记录"""
        self._ensure_loaded()
        return {url: VisitedEntry(**data) for url, data in self._data["urls"].items()}

    def get_stats(self) -> dict[str, int]:
        """获取统计信息"""
        self._ensure_loaded()
        stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
        for entry in self._data["urls"].values():
            stats["total"] += 1
            status = entry.get("status", "unknown")
            if status in stats:
                stats[status] += 1
        return stats

    def clear(self):
        """清空历史记录"""
        now = self._now_iso()
        self._data = {
            "version": "1.0",
            "created_at": now,
            "updated_at": now,
            "urls": {},
            "created_dirs": [],
        }
        self.save()

    def has_created_dir(self, dir_path: str | Path) -> bool:
        """检查目录是否是我们创建的"""
        self._ensure_loaded()
        resolved_path = str(Path(dir_path).resolve())
        return resolved_path in self._data["created_dirs"]

    def add_created_dir(self, dir_path: str | Path):
        """记录我们创建的目录"""
        self._ensure_loaded()
        resolved_path = str(Path(dir_path).resolve())
        if resolved_path not in self._data["created_dirs"]:
            self._data["created_dirs"].append(resolved_path)
            self.save()

    def get_created_dirs(self) -> list[Path]:
        """获取所有我们创建的目录列表"""
        self._ensure_loaded()
        return [Path(p) for p in self._data["created_dirs"]]

    def remove_created_dir(self, dir_path: str | Path) -> bool:
        """移除创建的目录记录，返回是否成功移除"""
        self._ensure_loaded()
        resolved_path = str(Path(dir_path).resolve())
        if resolved_path in self._data["created_dirs"]:
            self._data["created_dirs"].remove(resolved_path)
            self.save()
            return True
        return False


def get_user_config_dir() -> Path:
    """获取用户配置目录"""
    if sys.platform == "win32":
        # Windows: C:\Users\用户名\.qd_browser
        base_dir = Path.home() / ".qd_browser"
    else:
        # Linux/Mac: ~/.qd_browser
        base_dir = Path.home() / ".qd_browser"
    return base_dir


def get_history() -> URLHistory:
    """获取全局 URL 历史记录管理器"""
    history_path = get_user_config_dir() / "visited.json"
    return URLHistory(history_path)
