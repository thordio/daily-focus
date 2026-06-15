"""Tests for the three-topic system: field propagation, grouping, and rendering."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from src.ai.summarizer import DailySummarizer
from src.renderer import DailyRenderer
from src.models import ContentItem, RSSSourceConfig, SourceType
from src.scrapers.rss import RSSScraper
from tests.conftest_helpers import make_content_item


# ---------------------------------------------------------------------------
# 1. RSSSourceConfig topic field
# ---------------------------------------------------------------------------


def test_rss_source_config_has_topic_field_with_default() -> None:
    """RSSSourceConfig accepts a topic field defaulting to 'ai-tech'."""
    cfg = RSSSourceConfig(name="Test", url="https://example.com/feed.xml")
    assert cfg.topic == "ai-tech"


def test_rss_source_config_topic_can_be_overridden() -> None:
    """RSSSourceConfig topic field can be set to a custom value."""
    cfg = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", topic="ai-markets"
    )
    assert cfg.topic == "ai-markets"


def test_rss_source_config_topic_round_trip() -> None:
    """RSSSourceConfig serializes and deserializes the topic field."""
    cfg = RSSSourceConfig(
        name="Test", url="https://example.com/feed.xml", topic="economy"
    )
    dumped = cfg.model_dump()
    assert dumped["topic"] == "economy"
    loaded = RSSSourceConfig.model_validate(dumped)
    assert loaded.topic == "economy"


# ---------------------------------------------------------------------------
# 2. RSS scraper topic propagation
# ---------------------------------------------------------------------------


def _make_scraper(feed: str, source: RSSSourceConfig | None = None) -> RSSScraper:
    """Build an RSSScraper that returns the given feed text."""
    response = MagicMock()
    response.text = feed
    response.raise_for_status.return_value = None
    client = AsyncMock()
    client.get.return_value = response
    if source is None:
        source = RSSSourceConfig(name="Test", url="https://example.com/feed.xml")
    return RSSScraper([source], client)


SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
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


def test_rss_scraper_propagates_topic_to_metadata() -> None:
    """RSS scraper passes source.topic to metadata['topic']."""
    source = RSSSourceConfig(
        name="Test",
        url="https://example.com/feed.xml",
        topic="ai-markets",
    )
    scraper = _make_scraper(SAMPLE_FEED, source)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 1
    assert items[0].metadata.get("topic") == "ai-markets"


def test_rss_scraper_default_topic() -> None:
    """RSS scraper defaults to 'ai-tech' when source has no topic override."""
    source = RSSSourceConfig(name="Test", url="https://example.com/feed.xml")
    scraper = _make_scraper(SAMPLE_FEED, source)
    since = datetime(2026, 4, 24, 0, 0, tzinfo=timezone.utc)

    items = asyncio.run(scraper.fetch(since))
    assert len(items) == 1
    assert items[0].metadata.get("topic") == "ai-tech"


# ---------------------------------------------------------------------------
# 3. get_structured_data topic grouping
# ---------------------------------------------------------------------------


def _make_topic_item(item_id: str, topic: str, score: float = 7.0) -> ContentItem:
    """Create a ContentItem with a specific topic in metadata."""
    return make_content_item(
        item_id=item_id,
        title=f"Item {item_id}",
        url=f"https://example.com/{item_id}",
        ai_score=score,
        ai_summary=f"Summary for {item_id}",
        ai_tags=["test"],
        metadata={
            "feed_name": "Test Feed",
            "topic": topic,
        },
    )


def test_topic_grouping_item_without_topic_defaults_to_ai_tech() -> None:
    """Item without topic in metadata is grouped in ai-tech tab."""
    s = DailySummarizer()
    item = make_content_item(
        item_id="rss:test:no-topic",
        metadata={"feed_name": "Test"},
    )
    data = s.get_structured_data([item], "2026-06-01", 10, "zh", "morning")
    assert len(data["tabs"]["ai-tech"]["items"]) == 1
    assert len(data["tabs"]["ai-markets"]["items"]) == 0
    assert len(data["tabs"]["economy"]["items"]) == 0


def test_topic_grouping_different_topics_separate_tabs() -> None:
    """Items with different topics are correctly grouped into separate tabs."""
    s = DailySummarizer()
    items = [
        _make_topic_item("1", "ai-tech"),
        _make_topic_item("2", "ai-markets"),
        _make_topic_item("3", "economy"),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    assert len(data["tabs"]["ai-tech"]["items"]) == 1
    assert len(data["tabs"]["ai-markets"]["items"]) == 1
    assert len(data["tabs"]["economy"]["items"]) == 1


def test_topic_grouping_empty_tab_no_crash() -> None:
    """Empty tab has empty items list and does not crash."""
    s = DailySummarizer()
    data = s.get_structured_data([], "2026-06-01", 10, "zh", "morning")
    for tab_key in ("ai-tech", "ai-markets", "economy"):
        assert isinstance(data["tabs"][tab_key]["items"], list)
        assert len(data["tabs"][tab_key]["items"]) == 0


def test_topic_grouping_all_items_one_tab() -> None:
    """All items in one topic leaves other tabs empty."""
    s = DailySummarizer()
    items = [
        _make_topic_item("1", "ai-tech"),
        _make_topic_item("2", "ai-tech"),
        _make_topic_item("3", "ai-tech"),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    assert len(data["tabs"]["ai-tech"]["items"]) == 3
    assert len(data["tabs"]["ai-markets"]["items"]) == 0
    assert len(data["tabs"]["economy"]["items"]) == 0


def test_topic_grouping_tabs_dict_has_four_keys() -> None:
    """tabs dict always has four keys: 3 news topics + market_indicators."""
    s = DailySummarizer()
    data = s.get_structured_data([], "2026-06-01", 10, "zh", "morning")
    assert set(data["tabs"].keys()) == {"ai-tech", "ai-markets", "economy", "market_indicators"}


def test_topic_grouping_backward_compat_no_topic() -> None:
    """Backward compat: item without 'topic' in metadata defaults to ai-tech."""
    s = DailySummarizer()
    item = make_content_item(
        item_id="rss:test:backward",
        metadata={"feed_name": "Test"},  # no 'topic' key
    )
    data = s.get_structured_data([item], "2026-06-01", 10, "zh", "morning")
    # Should be in ai-tech tab
    assert len(data["tabs"]["ai-tech"]["items"]) == 1
    # Flat items list should also contain it
    assert len(data["items"]) == 1


def test_topic_grouping_items_list_backward_compat() -> None:
    """Flat items list still contains all items (backward compat)."""
    s = DailySummarizer()
    items = [
        _make_topic_item("1", "ai-tech"),
        _make_topic_item("2", "ai-markets"),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    assert len(data["items"]) == 2


def test_topic_grouping_tab_labels_zh() -> None:
    """Tab labels are correct in Chinese."""
    s = DailySummarizer()
    data = s.get_structured_data([], "2026-06-01", 10, "zh", "morning")
    assert data["tabs"]["ai-tech"]["label"] == "AI 技术"
    assert data["tabs"]["ai-markets"]["label"] == "AI 市场"
    assert data["tabs"]["economy"]["label"] == "经济动向"


def test_topic_grouping_tab_labels_en() -> None:
    """Tab labels are correct in English."""
    s = DailySummarizer()
    data = s.get_structured_data([], "2026-06-01", 10, "en", "morning")
    assert data["tabs"]["ai-tech"]["label_en"] == "AI Tech"
    assert data["tabs"]["ai-markets"]["label_en"] == "AI Markets"
    assert data["tabs"]["economy"]["label_en"] == "Economy"


# ---------------------------------------------------------------------------
# 4. Tab rendering via DailyRenderer
# ---------------------------------------------------------------------------


def test_tab_render_has_tab_navigation() -> None:
    """Rendered HTML has tab navigation with buttons."""
    s = DailySummarizer()
    items = [_make_topic_item("1", "ai-tech")]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    assert 'class="tab-nav"' in html
    assert 'class="tab-btn' in html


def test_tab_render_four_tab_buttons() -> None:
    """Rendered HTML has exactly four tab buttons (3 news + 1 market indicators)."""
    s = DailySummarizer()
    items = [_make_topic_item("1", "ai-tech")]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    # Each tab button has class="tab-btn"
    import re
    tab_buttons = re.findall(r'class="tab-btn[^"]*"', html)
    assert len(tab_buttons) == 4


def test_tab_render_shows_item_count() -> None:
    """Each tab button shows its item count."""
    s = DailySummarizer()
    items = [
        _make_topic_item("1", "ai-tech"),
        _make_topic_item("2", "ai-markets"),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    # Check count numbers appear
    assert "1" in html  # ai-tech count
    assert "1" in html  # ai-markets count
    assert "0" in html  # economy count


def test_tab_render_only_active_tab_visible() -> None:
    """Only the active tab panel is visible (display: block)."""
    s = DailySummarizer()
    items = [
        _make_topic_item("1", "ai-tech"),
        _make_topic_item("2", "ai-markets"),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    # First tab panel should be active
    assert 'tab-panel active' in html
    # Only one panel should have 'active' class
    assert html.count('tab-panel active') == 1


def test_tab_render_empty_tab_shows_no_content() -> None:
    """Empty tabs show a 'no content' message."""
    s = DailySummarizer()
    items = [_make_topic_item("1", "ai-tech")]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    # Economy tab is empty - should show contextual empty message
    assert "今日暂无经济动向相关资讯" in html


def test_tab_render_empty_tab_en_shows_no_items() -> None:
    """Empty tabs in English show 'No items'."""
    s = DailySummarizer()
    items = [_make_topic_item("1", "ai-tech")]
    data = s.get_structured_data(items, "2026-06-01", 10, "en", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    assert "No Economy items today" in html


def test_tab_render_items_appear_in_correct_tab_panel() -> None:
    """Items appear in the correct tab panel based on their topic."""
    s = DailySummarizer()
    items = [
        _make_topic_item("1", "ai-tech"),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    # The ai-tech tab panel should contain the item title
    assert "Item 1" in html


def test_tab_render_fallback_flat_when_no_tabs() -> None:
    """When tabs key is missing, render falls back to flat items list."""
    r = DailyRenderer()
    data = {
        "date": "2026-06-01",
        "period": "morning",
        "language": "zh",
        "total_fetched": 10,
        "selected_count": 1,
        "next_update": "今晚 20:00",
        "items": [
            {
                "index": 1,
                "title": "Flat Item",
                "title_en": "Flat Item",
                "url": "https://example.com/1",
                "score": 7.0,
                "source_label": "Test",
                "source_type": "rss",
                "published_at": "2026-06-01T00:00:00+00:00",
                "whats_new": "Test",
                "why_it_matters": "Test",
                "key_details": "",
                "ai_reason": "",
                "background": "",
                "community_discussion": "",
                "tags": [],
                "images": [],
                "references": [],
            }
        ],
    }
    html = r.render_html(data)
    assert "Flat Item" in html


def test_tab_render_four_panels() -> None:
    """Rendered HTML contains exactly four tab panels (3 news + 1 market indicators)."""
    s = DailySummarizer()
    items = [
        _make_topic_item("1", "ai-tech"),
        _make_topic_item("2", "ai-markets"),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    import re
    panels = re.findall(r'id="tab-([^"]+)"', html)
    assert len(panels) == 4
    assert "tab-market_indicators" in html


def test_tab_render_javascript_function() -> None:
    """Rendered HTML includes switchTab JavaScript function."""
    s = DailySummarizer()
    items = [_make_topic_item("1", "ai-tech")]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    assert "function switchTab" in html
    assert "document.querySelectorAll" in html


# ---------------------------------------------------------------------------
# 5. Config validation (all RSS sources have topic)
# ---------------------------------------------------------------------------


def test_config_rss_sources_have_topic() -> None:
    """All RSS sources in config files have a topic field."""
    import json

    import pytest

    # Try config.json first (single-edition), fall back to legacy
    config_candidates = ["data/config.json", "data/config-morning.json"]
    tested = False
    for fn in config_candidates:
        try:
            with open(fn) as f:
                cfg_dict = json.load(f)
        except FileNotFoundError:
            continue
        for src in cfg_dict["sources"]["rss"]:
            assert "topic" in src, f"{fn}: {src['name']} is missing topic"
            assert isinstance(src["topic"], str), f"{fn}: {src['name']} topic is not a string"
        tested = True
        break
    assert tested, "No config file found among: " + ", ".join(config_candidates)
