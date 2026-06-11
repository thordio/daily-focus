"""Tests for RSS scraper, including image extraction (Work Area F)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from src.models import RSSSourceConfig
from src.scrapers.rss import RSSScraper


def test_rss_ids_are_deterministic() -> None:
    feed = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Test</title>
      <item>
        <guid>entry-1</guid>
        <title>Item 1</title>
        <link>https://example.com/item-1</link>
        <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
        <description>Hello</description>
      </item>
    </channel></rss>
    """
    response = MagicMock()
    response.text = feed
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    source = RSSSourceConfig(name="Test", url="https://example.com/feed.xml")
    scraper = RSSScraper([source], client)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    first = asyncio.run(scraper.fetch(since))[0].id
    second = asyncio.run(scraper.fetch(since))[0].id

    assert first == second
    assert first == "rss:example.com_feed.xml:5e2d5d1e58e94d76"


def _make_scraper_for_feed(feed: str) -> RSSScraper:
    """Helper: build an RSSScraper that returns the given feed text."""
    response = MagicMock()
    response.text = feed
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    source = RSSSourceConfig(name="Test", url="https://example.com/feed.xml")
    return RSSScraper([source], client)


def test_rss_image_extraction_and_filtering() -> None:
    """RSS items with img tags extract candidate_images; logo URLs filtered."""
    feed = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Test</title>
      <item>
        <guid>entry-img-1</guid>
        <title>Chart heavy article</title>
        <link>https://example.com/charts</link>
        <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
        <description><![CDATA[
          <p>This article has charts and diagrams.</p>
          <img src="https://example.com/chart1.png" alt="GPT-5 vs Claude 4 benchmark comparison on MMLU" />
          <p>As we can see from the chart above, the performance gap is widening.</p>
          <img src="https://example.com/logo.png" alt="Company logo" />
          <p>Some more text after a decorative image.</p>
          <img src="https://example.com/avatar-sm.jpg" alt="Author avatar" />
        ]]></description>
      </item>
    </channel></rss>
    """
    scraper = _make_scraper_for_feed(feed)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 1
    item = items[0]

    candidates = item.metadata.get("candidate_images", [])
    # Only chart1.png should survive filtering (logo and avatar are skipped)
    assert len(candidates) == 1
    assert candidates[0]["url"] == "https://example.com/chart1.png"
    assert "benchmark" in candidates[0]["alt"]
    # Surrounding context should be non-empty
    assert len(candidates[0]["before"]) > 0 or len(candidates[0]["after"]) > 0


def test_rss_image_extraction_no_images() -> None:
    """RSS items without img tags get empty candidate_images list."""
    feed = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Test</title>
      <item>
        <guid>entry-noimg</guid>
        <title>Text only article</title>
        <link>https://example.com/text</link>
        <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
        <description>Just plain text content without any images.</description>
      </item>
    </channel></rss>
    """
    scraper = _make_scraper_for_feed(feed)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 1
    candidates = items[0].metadata.get("candidate_images", [])
    assert candidates == []


def test_rss_image_filter_button_and_headshot() -> None:
    """URLs containing 'button' or 'headshot' are filtered out."""
    feed = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Test</title>
      <item>
        <guid>entry-btns</guid>
        <title>Image filtering test</title>
        <link>https://example.com/filter</link>
        <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
        <description><![CDATA[
          <img src="https://example.com/submit-button.png" alt="Submit" />
          <img src="https://example.com/headshot-john.jpg" alt="John" />
          <img src="https://example.com/chart2.png" alt="Growth chart Q2 2026" />
        ]]></description>
      </item>
    </channel></rss>
    """
    scraper = _make_scraper_for_feed(feed)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    candidates = items[0].metadata.get("candidate_images", [])
    assert len(candidates) == 1
    assert "chart2.png" in candidates[0]["url"]


def test_rss_image_max_five_candidates() -> None:
    """At most 5 candidate images are kept per entry."""
    parts = ['<?xml version="1.0" encoding="UTF-8" ?>',
             '<rss version="2.0"><channel><title>Test</title>',
             '<item><guid>entry-many-imgs</guid><title>Many images</title>',
             '<link>https://example.com/many</link>',
             '<pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>',
             '<description><![CDATA[']
    for i in range(10):
        parts.append(f'<img src="https://example.com/img{i}.png" alt="Image {i}" />')
    parts.append(']]></description></item></channel></rss>')
    feed = "\n".join(parts)

    scraper = _make_scraper_for_feed(feed)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    candidates = items[0].metadata.get("candidate_images", [])
    assert len(candidates) == 5


def test_rss_image_extraction_multiple_items() -> None:
    """Multiple items in one feed each extract their own candidate images."""
    feed = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Test</title>
      <item>
        <guid>entry-a</guid>
        <title>Item A with chart</title>
        <link>https://example.com/a</link>
        <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
        <description><![CDATA[
          <img src="https://example.com/a-chart.png" alt="Chart A" />
        ]]></description>
      </item>
      <item>
        <guid>entry-b</guid>
        <title>Item B with logo</title>
        <link>https://example.com/b</link>
        <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
        <description><![CDATA[
          <img src="https://example.com/b-logo.png" alt="Logo B" />
        ]]></description>
      </item>
    </channel></rss>
    """
    scraper = _make_scraper_for_feed(feed)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 2
    # Item A should have its chart candidate (not filtered)
    assert len(items[0].metadata.get("candidate_images", [])) == 1
    # Item B's logo should be filtered out
    assert len(items[1].metadata.get("candidate_images", [])) == 0


def test_rss_image_extraction_icon_filtered() -> None:
    """URLs containing 'icon' are filtered out."""
    feed = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0"><channel><title>Test</title>
      <item>
        <guid>entry-icon</guid>
        <title>Icon test</title>
        <link>https://example.com/icon</link>
        <pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>
        <description><![CDATA[
          <img src="https://example.com/favicon.ico" alt="icon" />
          <img src="https://example.com/real-chart.png" alt="Real data" />
        ]]></description>
      </item>
    </channel></rss>
    """
    scraper = _make_scraper_for_feed(feed)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    candidates = items[0].metadata.get("candidate_images", [])
    assert len(candidates) == 1
    assert "real-chart.png" in candidates[0]["url"]


def test_rss_image_cache_dedup() -> None:
    """_load_image_cache returns a dict for counting seen URLs."""
    scraper = _make_scraper_for_feed("")
    cache = scraper._load_image_cache()
    assert isinstance(cache, dict)


# ---------------------------------------------------------------------------
# 6. Per-feed max_items cap
# ---------------------------------------------------------------------------


def test_rss_max_items_default_is_30() -> None:
    """RSSSourceConfig has max_items with default 30."""
    cfg = RSSSourceConfig(name="Test", url="https://example.com/feed.xml")
    assert cfg.max_items == 30


def test_rss_max_items_custom_value() -> None:
    """RSSSourceConfig accepts custom max_items value."""
    cfg = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", max_items=5
    )
    assert cfg.max_items == 5


def test_rss_max_items_round_trip() -> None:
    """max_items round-trips through serialization."""
    cfg = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", max_items=10
    )
    dumped = cfg.model_dump()
    assert dumped["max_items"] == 10
    loaded = RSSSourceConfig.model_validate(dumped)
    assert loaded.max_items == 10


def test_rss_max_items_model_validate() -> None:
    """max_items is parseable via model_validate."""
    data = {"name": "Test", "url": "https://example.com/feed.xml", "max_items": 3}
    cfg = RSSSourceConfig.model_validate(data)
    assert cfg.max_items == 3


def _make_feed_with_n_items(n: int) -> str:
    """Build an RSS feed XML string with ``n`` items."""
    parts = ['<?xml version="1.0" encoding="UTF-8" ?>',
             '<rss version="2.0"><channel><title>Test</title>']
    for i in range(n):
        parts.append(
            f'<item><guid>entry-{i}</guid><title>Item {i}</title>'
            f'<link>https://example.com/{i}</link>'
            f'<pubDate>Fri, 24 Apr 2026 12:00:00 GMT</pubDate>'
            f'<description>Content {i}</description></item>'
        )
    parts.append('</channel></rss>')
    return '\n'.join(parts)


def test_rss_max_items_cap_applied() -> None:
    """Scraper returns at most max_items items from a feed."""
    feed = _make_feed_with_n_items(10)
    response = MagicMock()
    response.text = feed
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response

    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", max_items=5
    )
    scraper = RSSScraper([source], client)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 5


def test_rss_max_items_no_padding() -> None:
    """If feed has fewer items than max_items, all are returned (no padding)."""
    feed = _make_feed_with_n_items(3)
    response = MagicMock()
    response.text = feed
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response

    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", max_items=10
    )
    scraper = RSSScraper([source], client)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 3  # not padded to 10


def test_rss_max_items_exact_match() -> None:
    """When feed has exactly max_items items, all are returned."""
    feed = _make_feed_with_n_items(5)
    response = MagicMock()
    response.text = feed
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response

    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", max_items=5
    )
    scraper = RSSScraper([source], client)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 5


def test_rss_max_items_zero_edge_case() -> None:
    """max_items=0 causes the scraper to return 0 items.

    The current implementation slices ``items[:0]`` when max_items is 0,
    which returns an empty list. This documents that behavior; if a
    different semantic is desired (e.g., 0 means "no limit"), the
    comment in ``RSSScraper._fetch_feed`` needs updating.
    """
    feed = _make_feed_with_n_items(5)
    response = MagicMock()
    response.text = feed
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response

    source = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", max_items=0
    )
    scraper = RSSScraper([source], client)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    # max_items=0 → slice [:0] → empty list
    assert len(items) == 0


def test_rss_max_items_per_feed_independent() -> None:
    """Different feeds have independent max_items caps."""
    feed_a = _make_feed_with_n_items(10)
    feed_b = _make_feed_with_n_items(5)

    response_a = MagicMock()
    response_a.text = feed_a
    response_a.raise_for_status.return_value = None
    response_b = MagicMock()
    response_b.text = feed_b
    response_b.raise_for_status.return_value = None

    client = AsyncMock()
    client.get.side_effect = [response_a, response_b]

    source_a = RSSSourceConfig(
        name="FeedA", url="https://example.com/feedA.xml", max_items=3
    )
    source_b = RSSSourceConfig(
        name="FeedB", url="https://example.com/feedB.xml", max_items=10
    )
    scraper = RSSScraper([source_a, source_b], client)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 8  # 3 capped from feed A + 5 from feed B
