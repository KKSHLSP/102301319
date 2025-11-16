"""Visualization utilities such as word cloud generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional, Sequence, Set

from wordcloud import WordCloud

try:  # pragma: no cover - optional dependency
    import jieba  # type: ignore
except Exception:  # pragma: no cover - fallback when jieba is missing
    jieba = None

from .analysis import build_dataframe
from .models import VideoDanmakuBundle

DEFAULT_STOPWORDS: Set[str] = {
    "",
    "哈哈哈",
    "哈哈",
    "哈哈哈哈",
    "感觉",
    "真的",
    "就是",
    "所以",
}

COMMON_FONT_CANDIDATES: Sequence[Path] = (
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/Library/Fonts/SourceHanSansCN-Regular.otf"),
    Path("C:/Windows/Fonts/msyh.ttc"),  # Microsoft YaHei
    Path("C:/Windows/Fonts/simhei.ttf"),
)


def _tokenize(content: str) -> Iterable[str]:
    if not content:
        return []
    if jieba is None:
        # naive fallback: keep original string without segmentation
        return (content,)
    return jieba.cut(content, cut_all=False)


_BAD_CHARS_PATTERN = re.compile(r"[^\w\u4e00-\u9fff]+")


def _clean_token(raw: str) -> str:
    """Normalize token by stripping whitespace and removing乱码/符号."""
    token = re.sub(r"\s+", "", raw)
    token = _BAD_CHARS_PATTERN.sub("", token)
    # drop replacement chars or empty tokens
    if not token or "\ufffd" in token:
        return ""
    return token


def _detect_font() -> Optional[Path]:
    """Pick the first available Chinese font on the system."""
    for candidate in COMMON_FONT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def generate_wordcloud(
    bundles: Sequence[VideoDanmakuBundle],
    *,
    output_path: Path,
    font_path: Optional[Path] = None,
    width: int = 1280,
    height: int = 720,
    background_color: str = "white",
    stopwords: Optional[Iterable[str]] = None,
) -> Path:
    """Generate a word cloud image from the danmaku corpus."""
    df = build_dataframe(bundles)
    if df.empty:
        raise ValueError("No danmaku data available to build a word cloud.")

    tokens: list[str] = []
    stopword_set = DEFAULT_STOPWORDS | set(stopwords or [])
    for content in df["content"].dropna():
        for token in _tokenize(str(content).strip()):
            token = _clean_token(token)
            # 跳过空串、停用词
            if not token or token in stopword_set:
                continue
            tokens.append(token)

    if not tokens:
        raise ValueError("Tokenization produced an empty corpus.")

    text_blob = " ".join(tokens)
    effective_font = font_path or _detect_font()

    wordcloud = WordCloud(
        font_path=str(effective_font) if effective_font else None,
        width=width,
        height=height,
        background_color=background_color,
        stopwords=stopword_set,
    ).generate(text_blob)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wordcloud.to_file(str(output_path))
    return output_path
