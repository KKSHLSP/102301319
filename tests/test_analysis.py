import json
from pathlib import Path

from danmaku_analysis.analysis import compute_statistics
from danmaku_analysis.models import VideoDanmakuBundle


def load_sample_bundle() -> VideoDanmakuBundle:
    sample_path = Path(__file__).parent / "data" / "sample_bundle.json"
    return VideoDanmakuBundle.from_dict(json.loads(sample_path.read_text(encoding="utf-8")))


def test_compute_statistics_top_contents() -> None:
    bundle = load_sample_bundle()
    stats = compute_statistics([bundle], top_n=2)

    assert len(stats.top_contents) == 2
    assert stats.top_contents.iloc[0]["content"] == "大模型真是生产力工具！"
    assert stats.top_contents.iloc[0]["count"] == 1


def test_keyword_distribution_single_keyword() -> None:
    bundle = load_sample_bundle()
    stats = compute_statistics([bundle], top_n=8)

    assert stats.keyword_counts.iloc[0]["keyword"] == "大语言模型"
    assert stats.keyword_counts.iloc[0]["count"] == len(bundle.danmaku)
