"""Tests for RSS scraper, including image extraction (Work Area F)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

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
