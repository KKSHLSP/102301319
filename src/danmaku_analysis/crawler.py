"""Crawler implementation for fetching B 站弹幕数据."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Optional, Set
from xml.etree import ElementTree as ET

import httpx

from .config import CrawlerConfig, PathConfig
from .models import DanmakuRecord, VideoDanmakuBundle, VideoMetadata
from .persistence import bundle_path, dump_bundle, load_bundle


SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
VIEW_API = "https://api.bilibili.com/x/web-interface/view"
DM_LIST_API = "https://api.bilibili.com/x/v1/dm/list.so"

logger = logging.getLogger(__name__)


class BilibiliCrawler:
    """A lightweight crawler tailored for danmaku scraping."""

    def __init__(self, config: CrawlerConfig, paths: PathConfig):
        self.config = config
        self.paths = paths
        self.paths.ensure_directories()
        self._semaphore = asyncio.Semaphore(max(1, self.config.concurrent_requests))

    async def crawl(self) -> List[VideoDanmakuBundle]:
        bundles: List[VideoDanmakuBundle] = []
        per_keyword = max(1, self.config.max_videos // max(1, len(self.config.keywords)))

        cookies = self.config.build_cookies()
        timeout = httpx.Timeout(self.config.request_timeout)

        async with httpx.AsyncClient(
            headers=self.config.build_headers(),
            cookies=cookies,
            timeout=timeout,
        ) as client:
            tasks = []
            ranking_index = 0
            seen_bvids: Set[str] = set()
            for keyword in self.config.keywords_iter():
                search_results = await self._search_keyword(client, keyword, per_keyword)
                for result in search_results:
                    bvid = result.get("bvid")
                    if not bvid or bvid in seen_bvids:
                        continue
                    seen_bvids.add(bvid)
                    ranking_index += 1
                    tasks.append(
                        self._bounded_collect_video_bundle(
                            client,
                            result,
                            keyword=keyword,
                            ranking_index=ranking_index,
                        )
                    )

            for coro in asyncio.as_completed(tasks):
                bundle = await coro
                if bundle:
                    bundles.append(bundle)

        return bundles

    async def _bounded_collect_video_bundle(
        self,
        client: httpx.AsyncClient,
        search_item: Dict[str, Any],
        *,
        keyword: str,
        ranking_index: int,
    ) -> Optional[VideoDanmakuBundle]:
        """Run _collect_video_bundle under a semaphore to cap concurrency."""
        async with self._semaphore:
            return await self._collect_video_bundle(
                client,
                search_item,
                keyword=keyword,
                ranking_index=ranking_index,
            )

    async def _search_keyword(
        self, client: httpx.AsyncClient, keyword: str, per_keyword: int
    ) -> List[Dict[str, Any]]:
        """Return search results for a keyword."""
        results: List[Dict[str, Any]] = []
        page = 1
        while len(results) < per_keyword:
            params = {
                "search_type": "video",
                "keyword": keyword,
                "page": page,
                "order": self.config.order,
            }
            payload = await self._request_json(client, SEARCH_API, params=params)
            items = (payload.get("data") or {}).get("result") or []
            if not items:
                break
            for item in items:
                results.append(item)
                if len(results) >= per_keyword or len(results) >= self.config.max_videos:
                    break
            page += 1
            if self.config.pages_per_keyword and page > self.config.pages_per_keyword:
                break
        return results[:per_keyword]

    async def _collect_video_bundle(
        self,
        client: httpx.AsyncClient,
        search_item: Dict[str, Any],
        *,
        keyword: str,
        ranking_index: int,
    ) -> Optional[VideoDanmakuBundle]:
        """Fetch metadata + danmaku for a single search result."""
        bvid = search_item.get("bvid")
        if not bvid:
            logger.debug("Search result missing bvid: %s", search_item)
            return None

        cached_path = bundle_path(self.paths.raw_dir, bvid)
        if self.config.enable_cache and cached_path.exists():
            logger.info("Cache hit for %s", bvid)
            return load_bundle(cached_path)

        try:
            view_payload = await self._request_json(
                client,
                VIEW_API,
                params={"bvid": bvid},
                headers=self._build_video_headers(bvid),
            )
        except httpx.HTTPStatusError as exc:
            logger.warning("Skip %s due to HTTP %s", bvid, exc.response.status_code)
            return None
        data = view_payload.get("data")
        if not data:
            logger.warning("No view data for %s", bvid)
            return None

        cid = data.get("cid")
        if cid is None:
            logger.warning("No cid for %s", bvid)
            return None

        metadata = VideoMetadata.from_view_api(
            data, keyword=keyword, cid=int(cid), ranking_index=ranking_index
        )

        try:
            danmaku_nodes = await self._fetch_danmaku(
                client, cid=int(cid), bvid=metadata.bvid
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Failed to fetch danmaku for %s (cid=%s): HTTP %s",
                metadata.bvid,
                cid,
                exc.response.status_code,
            )
            danmaku_nodes = []
        danmaku_records = [
            DanmakuRecord.from_xml_node(node=node, bvid=metadata.bvid, cid=metadata.cid)
            for node in danmaku_nodes
        ]

        bundle = VideoDanmakuBundle(video=metadata, danmaku=danmaku_records)
        if self.config.enable_cache:
            dump_bundle(bundle, self.paths)
        return bundle

    async def _fetch_danmaku(
        self, client: httpx.AsyncClient, cid: int, *, bvid: str
    ) -> Iterable[Any]:
        """Download and parse the XML danmaku list for a cid."""
        params = {"oid": cid}
        response = await self._request(
            client,
            DM_LIST_API,
            params=params,
            headers=self._build_video_headers(bvid),
        )
        response.encoding = "utf-8"
        xml_root = ET.fromstring(response.text)
        return xml_root.findall("d")

    async def _request(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """HTTP GET with simple retry + optional sleep decorator."""
        attempts = 0
        while True:
            try:
                if self.config.sleep_interval:
                    await asyncio.sleep(self.config.sleep_interval)
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response
            except Exception as exc:  # pragma: no cover - defensive branch
                attempts += 1
                if attempts >= self.config.retry_attempts:
                    logger.error("Request failed for %s params=%s: %s", url, params, exc)
                    raise
                await asyncio.sleep(1.5 * attempts)

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        response = await self._request(client, url, params=params, headers=headers)
        return response.json()

    def _build_video_headers(self, bvid: str) -> Dict[str, str]:
        headers = self.config.build_headers().copy()
        headers["Referer"] = f"https://www.bilibili.com/video/{bvid}"
        return headers


def crawl(config: CrawlerConfig, paths: PathConfig) -> List[VideoDanmakuBundle]:
    """Public synchronous helper that runs the crawler."""
    crawler = BilibiliCrawler(config=config, paths=paths)
    return asyncio.run(crawler.crawl())
