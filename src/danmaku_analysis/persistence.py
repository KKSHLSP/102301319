"""Persistence helpers for reading/writing intermediate data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, List

from .config import PathConfig
from .models import VideoDanmakuBundle


def bundle_path(raw_dir: Path, bvid: str) -> Path:
    return raw_dir / f"{bvid}.json"


def dump_bundle(bundle: VideoDanmakuBundle, paths: PathConfig) -> Path:
    """Persist a bundle to disk."""
    paths.ensure_directories()
    json_path = bundle_path(paths.raw_dir, bundle.video.bvid)
    json_path.write_text(json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


def load_bundle(path: Path) -> VideoDanmakuBundle:
    """Load a single bundle from disk."""
    return VideoDanmakuBundle.from_dict(json.loads(path.read_text(encoding="utf-8")))


def iter_bundles(raw_dir: Path) -> Iterator[VideoDanmakuBundle]:
    """Yield all bundles stored in raw_dir."""
    for json_file in sorted(raw_dir.glob("*.json")):
        yield load_bundle(json_file)


def load_all(paths: PathConfig) -> List[VideoDanmakuBundle]:
    """Convenience helper returning all bundles."""
    if not paths.raw_dir.exists():
        return []
    return list(iter_bundles(paths.raw_dir))
