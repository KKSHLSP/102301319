"""Typer based CLI entry-point."""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from pathlib import Path
from typing import Optional

import typer

import httpx

from .analysis import compute_statistics, export_to_excel
from .config import ProjectSettings, settings
from .crawler import BilibiliCrawler
from .persistence import bundle_path, load_all
from .visualization import generate_wordcloud

app = typer.Typer(help="Danmaku analysis toolkit commands.")


@app.command()
def fetch(
    max_videos: Optional[int] = typer.Option(
        None, help="Override the global max_videos limit."
    ),
    concurrency: Optional[int] = typer.Option(
        None, help="Limit concurrent requests to avoid 412."
    ),
    sleep_interval: Optional[float] = typer.Option(
        None, help="Sleep interval (seconds) between requests."
    ),
    pages: Optional[int] = typer.Option(
        None, help="Limit pages per keyword to cut traffic."
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Disable local caching for this run."
    ),
) -> None:
    """Fetch danmaku data from B 站 according to the configured keywords."""
    project_settings = _build_settings(
        max_videos=max_videos,
        enable_cache=not no_cache,
        concurrency=concurrency,
        sleep_interval=sleep_interval,
        pages=pages,
    )
    crawler = BilibiliCrawler(project_settings.crawler, project_settings.paths)
    try:
        bundles = asyncio.run(crawler.crawl())
    except httpx.HTTPStatusError as exc:
        typer.secho(
            f"HTTP {exc.response.status_code} when requesting {exc.request.url}. "
            "B 站可能触发了风控，请尝试：\n"
            "1. 在浏览器登录后复制完整 Cookie，设置环境变量 BILIBILI_COOKIE，再次运行。\n"
            "2. 降低请求速度或稍后再试。",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(f"Fetched {len(bundles)} video bundles.")


@app.command()
def analyze(
    top_n: int = typer.Option(8, help="Number of top danmaku entries to keep."),
    excel_path: Optional[Path] = typer.Option(
        None, help="Optional override for the Excel export path."
    ),
) -> None:
    """Compute danmaku statistics and export them to Excel."""
    project_settings = _build_settings(max_videos=None, enable_cache=True)
    bundles = load_all(project_settings.paths)
    if not bundles:
        typer.echo("No danmaku bundles found. Run the fetch command or seed-sample first.")
        raise typer.Exit(code=1)

    stats = compute_statistics(bundles, top_n=top_n)
    output_path = excel_path or (project_settings.paths.reports_dir / "danmaku_stats.xlsx")
    export_to_excel(stats=stats, output_path=output_path)
    typer.echo(f"Statistics exported to {output_path}")


@app.command()
def visualize(
    font_path: Optional[Path] = typer.Option(
        None, help="Optional font path to improve Chinese rendering."
    ),
    image_path: Optional[Path] = typer.Option(
        None, help="Override the default location for the generated word cloud."
    ),
    width: int = typer.Option(1280, help="Output image width."),
    height: int = typer.Option(720, help="Output image height."),
) -> None:
    """Generate a word cloud image from collected danmaku."""
    project_settings = _build_settings(max_videos=None, enable_cache=True)
    bundles = load_all(project_settings.paths)
    if not bundles:
        typer.echo("No danmaku bundles found. Run fetch or seed-sample first.")
        raise typer.Exit(code=1)

    output_path = image_path or (project_settings.paths.reports_dir / "danmaku_wordcloud.png")
    generate_wordcloud(
        bundles,
        output_path=output_path,
        font_path=font_path,
        width=width,
        height=height,
    )
    typer.echo(f"Word cloud generated at {output_path}")


@app.command()
def pipeline(
    max_videos: Optional[int] = typer.Option(
        None, help="Override max_videos before running the full pipeline."
    ),
    concurrency: Optional[int] = typer.Option(
        None, help="Limit concurrent requests to avoid 412."
    ),
    sleep_interval: Optional[float] = typer.Option(
        None, help="Sleep interval (seconds) between requests."
    ),
    pages: Optional[int] = typer.Option(
        None, help="Limit pages per keyword to cut traffic."
    ),
    top_n: int = typer.Option(8, help="Number of top danmaku entries to keep."),
    font_path: Optional[Path] = typer.Option(
        None, help="Font path for word cloud rendering."
    ),
    width: int = typer.Option(1280, help="Word cloud image width."),
    height: int = typer.Option(720, help="Word cloud image height."),
) -> None:
    """
    Run fetch -> analyze -> visualize in one go.

    This is the quickest way to完成题目要求的数据获取、统计和词云生成。
    """
    project_settings = _build_settings(
        max_videos=max_videos,
        enable_cache=True,
        concurrency=concurrency,
        sleep_interval=sleep_interval,
        pages=pages,
    )
    crawler = BilibiliCrawler(project_settings.crawler, project_settings.paths)
    try:
        bundles = asyncio.run(crawler.crawl())
    except httpx.HTTPStatusError as exc:
        typer.secho(
            f"HTTP {exc.response.status_code} when requesting {exc.request.url}. "
            "B 站可能触发了风控，请尝试设置 BILIBILI_COOKIE，并调低 max_videos 或增加 sleep_interval。",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    if not bundles:
        typer.secho("未能获取到任何弹幕，请检查关键词、网络或 Cookie。", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Fetched {len(bundles)} video bundles,开始统计...")
    stats = compute_statistics(bundles, top_n=top_n)
    reports_dir = project_settings.paths.reports_dir
    excel_path = reports_dir / "danmaku_stats.xlsx"
    export_to_excel(stats=stats, output_path=excel_path)
    typer.echo(f"Statistics exported to {excel_path}")

    image_path = reports_dir / "danmaku_wordcloud.png"
    try:
        generate_wordcloud(
            bundles,
            output_path=image_path,
            font_path=font_path,
            width=width,
            height=height,
        )
    except ValueError as exc:
        typer.secho(f"词云生成失败：{exc}", fg=typer.colors.YELLOW, err=True)
    else:
        typer.echo(f"Word cloud generated at {image_path}")

    typer.echo("Pipeline finished.")


@app.command("seed-sample")
def seed_sample() -> None:
    """Copy bundled sample data into the raw data directory for offline work."""
    project_settings = _build_settings(max_videos=None, enable_cache=True)
    base_dir = project_settings.paths.base_dir
    sample_path = base_dir / "tests" / "data" / "sample_bundle.json"
    if not sample_path.exists():
        typer.secho(
            f"Sample bundle not found at {sample_path}. Make sure tests/data/sample_bundle.json exists.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    project_settings.paths.ensure_directories()
    target = bundle_path(project_settings.paths.raw_dir, "sample_bundle")
    target.write_text(sample_path.read_text(encoding="utf-8"), encoding="utf-8")
    typer.echo(f"Sample bundle copied to {target}.")


def _build_settings(
    *,
    max_videos: Optional[int],
    enable_cache: bool,
    concurrency: Optional[int] = None,
    sleep_interval: Optional[float] = None,
    pages: Optional[int] = None,
) -> ProjectSettings:
    crawler_cfg = settings.crawler
    extra_cookie = os.getenv("BILIBILI_COOKIE")
    if (
        max_videos is not None
        or not enable_cache
        or extra_cookie
        or concurrency is not None
        or sleep_interval is not None
        or pages is not None
    ):
        crawler_cfg = replace(
            crawler_cfg,
            max_videos=max_videos or crawler_cfg.max_videos,
            enable_cache=enable_cache,
            cookie=extra_cookie or crawler_cfg.cookie,
            concurrent_requests=concurrency or crawler_cfg.concurrent_requests,
            sleep_interval=sleep_interval if sleep_interval is not None else crawler_cfg.sleep_interval,
            pages_per_keyword=pages if pages is not None else crawler_cfg.pages_per_keyword,
        )
    return ProjectSettings(paths=settings.paths, crawler=crawler_cfg)


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
