"""Runtime configuration for the danmaku analysis project."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
import uuid
from typing import Dict, Iterable, List, Sequence


BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class PathConfig:
    """Filesystem paths the pipeline writes to."""

    base_dir: Path = BASE_DIR
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")
    raw_dir: Path = field(default_factory=lambda: BASE_DIR / "data" / "raw")
    processed_dir: Path = field(default_factory=lambda: BASE_DIR / "data" / "processed")
    reports_dir: Path = field(default_factory=lambda: BASE_DIR / "data" / "reports")

    def ensure_directories(self) -> None:
        """Create directories if they do not exist."""
        for path in (self.data_dir, self.raw_dir, self.processed_dir, self.reports_dir):
            path.mkdir(parents=True, exist_ok=True)


DEFAULT_KEYWORDS: Sequence[str] = ("大语言模型", "大模型", "LLM")
# 留空默认 Cookie，避免携带无效或过期凭据。需要登录态时请通过
# 环境变量 BILIBILI_COOKIE 提供完整的 Cookie 串。
DEFAULT_COOKIE: str | None = None


@dataclass(slots=True)
class CrawlerConfig:
    """Configuration knobs for the B 站 crawler."""

    keywords: List[str] = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    max_videos: int = 360
    order: str = "totalrank"
    pages_per_keyword: int | None = None
    concurrent_requests: int = 2
    request_timeout: float = 10.0
    retry_attempts: int = 3
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    sleep_interval: float = 0.4
    enable_cache: bool = True
    referer: str = "https://www.bilibili.com"
    accept_language: str = "zh-CN,zh;q=0.9,en;q=0.8"
    cookie: str | None = field(default_factory=lambda: DEFAULT_COOKIE)

    def keywords_iter(self) -> Iterable[str]:
        for keyword in self.keywords:
            yield keyword

    def build_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Referer": self.referer,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": self.accept_language,
            "Connection": "keep-alive",
        }
        return headers

    def build_cookies(self) -> Dict[str, str]:
        jar: Dict[str, str] = {}
        if self.cookie:
            for part in self.cookie.split(";"):
                if not part.strip():
                    continue
                if "=" not in part:
                    continue
                name, value = part.split("=", 1)
                jar[name.strip()] = value.strip()
            return jar

        # 无外部 Cookie 时生成轻量级浏览器指纹，帮助规避部分 412 限制
        fake_buvid = f"{uuid.uuid4().hex[:32].upper()}infoc"
        now = int(time.time())
        jar.update(
            {
                "buvid3": fake_buvid,
                "b_nut": str(now),
                "i-wanna-go-back": "-1",
            }
        )
        return jar


@dataclass(slots=True)
class ProjectSettings:
    """Aggregate configuration used across modules."""

    paths: PathConfig = field(default_factory=PathConfig)
    crawler: CrawlerConfig = field(default_factory=CrawlerConfig)


settings = ProjectSettings()
