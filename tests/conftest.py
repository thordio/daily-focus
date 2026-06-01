from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _reset_image_cache(monkeypatch):
    """Isolate tests from the real image cache file to prevent cross-test pollution."""
    cache_file = ROOT / "data" / "image_cache.json"
    monkeypatch.setattr(
        "src.scrapers.rss.RSSScraper._load_image_cache",
        lambda self: {},
    )
    monkeypatch.setattr(
        "src.scrapers.rss.RSSScraper._save_image_cache",
        lambda self, cache: None,
    )
