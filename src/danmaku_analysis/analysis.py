"""Data analysis utilities for danmaku datasets."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

import pandas as pd

from .config import PathConfig
from .models import DanmakuRecord, VideoDanmakuBundle


@dataclass(slots=True)
class DanmakuStats:
    """Container for frequently used aggregated outputs."""

    dataframe: pd.DataFrame
    top_contents: pd.DataFrame
    keyword_counts: pd.DataFrame


def build_dataframe(bundles: Iterable[VideoDanmakuBundle]) -> pd.DataFrame:
    """Flatten bundles into a tabular pandas DataFrame."""
    records: List[dict] = []
    for bundle in bundles:
        for record in bundle.danmaku:
            records.append(
                {
                    "video_bvid": bundle.video.bvid,
                    "video_title": bundle.video.title,
                    "keyword": bundle.video.keyword,
                    "content": record.content.strip(),
                    "appear_time": record.appear_time,
                    "send_time": record.send_time.replace(tzinfo=None),
                    "mode": record.mode,
                    "font_size": record.font_size,
                    "font_color": record.font_color,
                    "author_hash": record.author_hash,
                    "pool": record.pool,
                }
            )
    return pd.DataFrame.from_records(records)


def compute_top_contents(df: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    """Return frequency counts for the most common danmaku content."""
    if df.empty:
        return pd.DataFrame(columns=["content", "count"])
    cleaned = (
        df.assign(content=df["content"].str.strip())
        .loc[lambda frame: frame["content"] != ""]
        .copy()
    )
    if cleaned.empty:
        return pd.DataFrame(columns=["content", "count"])

    aggregated = (
        cleaned.groupby("content")
        .agg(
            count=("content", "size"),
            first_seen=("send_time", "min"),
        )
        .sort_values(["count", "first_seen"], ascending=[False, True])
        .head(top_n)
        .reset_index()
    )
    return aggregated[["content", "count"]]


def compute_keyword_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate danmaku counts per search keyword."""
    if df.empty:
        return pd.DataFrame(columns=["keyword", "count"])
    return (
        df.groupby("keyword")
        .size()
        .sort_values(ascending=False)
        .reset_index(name="count")
    )


def export_to_excel(
    *,
    stats: DanmakuStats,
    output_path: Path,
) -> Path:
    """Persist aggregated statistics to an Excel workbook."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        stats.dataframe.to_excel(writer, sheet_name="danmaku", index=False)
        stats.top_contents.to_excel(writer, sheet_name="top_contents", index=False)
        stats.keyword_counts.to_excel(writer, sheet_name="keyword_counts", index=False)
    return output_path


def compute_statistics(bundles: Iterable[VideoDanmakuBundle], *, top_n: int = 8) -> DanmakuStats:
    """High level helper performing the most common aggregations."""
    df = build_dataframe(bundles)
    top_contents = compute_top_contents(df, top_n=top_n)
    keyword_counts = compute_keyword_distribution(df)
    return DanmakuStats(
        dataframe=df,
        top_contents=top_contents,
        keyword_counts=keyword_counts,
    )
