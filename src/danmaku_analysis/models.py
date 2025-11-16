"""Domain models shared across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


def _parse_timestamp(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class VideoMetadata:
    """Minimal subset of video metadata we care about."""

    aid: int
    bvid: str
    cid: int
    title: str
    keyword: str
    duration: int | None = None
    publish_time: datetime | None = None
    owner_name: str | None = None
    view_count: int | None = None
    danmaku_count: int | None = None
    like_count: int | None = None
    ranking_index: int | None = None

    @classmethod
    def from_view_api(
        cls,
        payload: Dict[str, Any],
        keyword: str,
        cid: int,
        ranking_index: int | None = None,
    ) -> "VideoMetadata":
        stat = payload.get("stat") or {}
        owner = payload.get("owner") or {}
        pubdate = payload.get("pubdate")
        publish_time = _parse_timestamp(pubdate) if pubdate else None
        return cls(
            aid=int(payload["aid"]),
            bvid=str(payload["bvid"]),
            cid=int(cid),
            title=str(payload.get("title", "")),
            keyword=keyword,
            duration=int(payload.get("duration") or 0) or None,
            publish_time=publish_time,
            owner_name=owner.get("name"),
            view_count=stat.get("view"),
            danmaku_count=stat.get("danmaku"),
            like_count=stat.get("like"),
            ranking_index=ranking_index,
        )


@dataclass(slots=True)
class DanmakuRecord:
    """Simplified representation of a danmaku bullet comment."""

    video_bvid: str
    video_cid: int
    content: str
    appear_time: float
    send_time: datetime
    mode: int
    font_size: int
    font_color: int
    author_hash: str | None
    weight: int | None = None
    pool: int | None = None

    @classmethod
    def from_xml_node(cls, *, node: Any, bvid: str, cid: int) -> "DanmakuRecord":
        """
        Parse a danmaku record from the B 站 XML format.

        Each <d> node contains an attribute p with comma separated payload:
        time,mode,font_size,font_color,send_time,midHash,pool,weight, ...
        """
        attrs = (node.attrib.get("p") or "").split(",")
        if len(attrs) < 7:
            raise ValueError("Unexpected danmaku payload")
        appear_time = float(attrs[0])
        mode = int(attrs[1])
        font_size = int(attrs[2])
        font_color = int(attrs[3])
        send_ts = float(attrs[4])
        author_hash = attrs[5] or None
        pool = _safe_int(attrs[6])
        weight = _safe_int(attrs[7]) if len(attrs) > 7 else None

        return cls(
            video_bvid=bvid,
            video_cid=cid,
            content=node.text or "",
            appear_time=appear_time,
            send_time=_parse_timestamp(send_ts),
            mode=mode,
            font_size=font_size,
            font_color=font_color,
            author_hash=author_hash,
            weight=weight,
            pool=pool,
        )


@dataclass(slots=True)
class VideoDanmakuBundle:
    """Bundle metadata together with its danmaku list."""

    video: VideoMetadata
    danmaku: List[DanmakuRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video": {
                "aid": self.video.aid,
                "bvid": self.video.bvid,
                "cid": self.video.cid,
                "title": self.video.title,
                "keyword": self.video.keyword,
                "duration": self.video.duration,
                "publish_time": self.video.publish_time.isoformat()
                if self.video.publish_time
                else None,
                "owner_name": self.video.owner_name,
                "view_count": self.video.view_count,
                "danmaku_count": self.video.danmaku_count,
                "like_count": self.video.like_count,
                "ranking_index": self.video.ranking_index,
            },
            "danmaku": [
                {
                    "video_bvid": record.video_bvid,
                    "video_cid": record.video_cid,
                    "content": record.content,
                    "appear_time": record.appear_time,
                    "send_time": record.send_time.isoformat(),
                    "mode": record.mode,
                    "font_size": record.font_size,
                    "font_color": record.font_color,
                    "author_hash": record.author_hash,
                    "weight": record.weight,
                    "pool": record.pool,
                }
                for record in self.danmaku
            ],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "VideoDanmakuBundle":
        video = payload["video"]
        danmaku_list = payload.get("danmaku", [])

        metadata = VideoMetadata(
            aid=video["aid"],
            bvid=video["bvid"],
            cid=video["cid"],
            title=video["title"],
            keyword=video["keyword"],
            duration=video.get("duration"),
            publish_time=datetime.fromisoformat(video["publish_time"])
            if video.get("publish_time")
            else None,
            owner_name=video.get("owner_name"),
            view_count=video.get("view_count"),
            danmaku_count=video.get("danmaku_count"),
            like_count=video.get("like_count"),
            ranking_index=video.get("ranking_index"),
        )

        records = [
            DanmakuRecord(
                video_bvid=item["video_bvid"],
                video_cid=item["video_cid"],
                content=item["content"],
                appear_time=item["appear_time"],
                send_time=datetime.fromisoformat(item["send_time"]),
                mode=item["mode"],
                font_size=item["font_size"],
                font_color=item["font_color"],
                author_hash=item.get("author_hash"),
                weight=item.get("weight"),
                pool=item.get("pool"),
            )
            for item in danmaku_list
        ]

        return cls(video=metadata, danmaku=records)
