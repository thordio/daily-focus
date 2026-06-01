"""Unit tests for DailyRenderer and DailySummarizer.get_structured_data()."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from src.ai.summarizer import DailySummarizer
from src.renderer import DailyRenderer
from tests.conftest_helpers import make_content_item


def make_sample_items():
    """Return a list of ContentItems with realistic bilingual metadata."""
    return [
        make_content_item(
            item_id="rss:test:1",
            title="OpenAI 正式发布 GPT-5",
            url="https://example.com/gpt5",
            ai_score=9.2,
            ai_summary="OpenAI 正式发布了 GPT-5，性能大幅提升。",
            ai_reason="重大模型发布，将改变 AI 行业格局。",
            ai_tags=["AI", "OpenAI", "GPT-5"],
            metadata={
                "title_en": "OpenAI Releases GPT-5",
                "feed_name": "TechCrunch",
                "detailed_summary_zh": "OpenAI 今天正式发布了 GPT-5 大语言模型。",
                "detailed_summary_en": "OpenAI released GPT-5 today.",
                "background_zh": "GPT-5 是第五代大模型。",
                "background_en": "GPT-5 is the fifth generation LLM.",
                "selected_images": [
                    {"url": "https://example.com/img.png", "alt": "Benchmark"}
                ],
                "sources": [
                    {"title": "OpenAI Blog", "url": "https://openai.com/blog"}
                ],
            },
        ),
        make_content_item(
            item_id="rss:test:2",
            title="DeepSeek 发布 V4",
            url="https://example.com/deepseek-v4",
            ai_score=7.5,
            ai_summary="DeepSeek 发布了 V4 模型。",
            ai_reason="重要的开源模型发布。",
            ai_tags=["AI", "DeepSeek"],
            metadata={
                "title_en": "DeepSeek Releases V4",
                "feed_name": "机器之心",
                "detailed_summary_zh": "DeepSeek 今天发布了 V4 模型。",
                "detailed_summary_en": "DeepSeek released V4 model today.",
                "community_discussion_zh": "开源社区热烈讨论。",
                "community_discussion_en": "Open-source community is excited.",
            },
        ),
    ]


def make_single_item_no_optional():
    """Return a single ContentItem with NO optional fields (no tags, no images, no discussion)."""
    return [
        make_content_item(
            item_id="rss:test:sparse",
            title="Sparse Item",
            url="https://example.com/sparse",
            ai_score=6.0,
            ai_summary="A minimal item.",
            ai_reason="A test item with nothing extra.",
            ai_tags=[],
            metadata={
                "title_en": "Sparse Item EN",
                "detailed_summary_zh": "最小条目。",
                "detailed_summary_en": "Minimal item.",
            },
        )
    ]


def make_very_long_title_item():
    """Return a ContentItem with a very long title (>200 chars)."""
    long_title = "非常" * 100 + "长的标题"
    assert len(long_title) > 200
    return [
        make_content_item(
            item_id="rss:test:long",
            title=long_title,
            url="https://example.com/long-title",
            ai_score=6.5,
            ai_summary="Long title test.",
            ai_reason="Just a test.",
            ai_tags=["test"],
            metadata={
                "title_en": "An extremely long title " * 15,
                "feed_name": "Test Feed",
                "detailed_summary_zh": "测试长标题。",
                "detailed_summary_en": "Testing long title.",
            },
        )
    ]


# --- get_structured_data tests ---


def test_structured_data_fields():
    """get_structured_data returns all required top-level fields."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")

    assert data["date"] == "2026-06-01"
    assert data["period"] == "morning"
    assert data["language"] == "zh"
    assert data["total_fetched"] == 50
    assert data["selected_count"] == 2
    assert data["next_update"] == "今晚 20:00"


def test_structured_data_next_update():
    """next_update varies by period and language."""
    s = DailySummarizer()
    items = make_sample_items()

    # morning/zh
    assert s.get_structured_data(items, "d", 10, "zh", "morning")["next_update"] == "今晚 20:00"
    # morning/en
    assert s.get_structured_data(items, "d", 10, "en", "morning")["next_update"] == "Tonight 20:00"
    # evening/zh
    assert s.get_structured_data(items, "d", 10, "zh", "evening")["next_update"] == "明早 08:00"
    # evening/en
    assert s.get_structured_data(items, "d", 10, "en", "evening")["next_update"] == "Tomorrow 08:00"


def test_structured_data_item_fields():
    """Each item dict contains all required keys."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")

    REQUIRED_ITEM_KEYS = {
        "index", "title", "title_en", "url", "score",
        "source_label", "source_type", "published_at",
        "whats_new", "why_it_matters", "key_details",
        "background", "community_discussion",
        "tags", "images", "references",
    }

    for item in data["items"]:
        assert set(item.keys()) == REQUIRED_ITEM_KEYS, (
            f"Missing keys: {REQUIRED_ITEM_KEYS - set(item.keys())}"
        )


def test_structured_data_first_item_values():
    """Verify first item's field values are correct."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")

    first = data["items"][0]
    assert first["index"] == 1
    assert first["title"] == "OpenAI 正式发布 GPT-5"
    assert first["title_en"] == "OpenAI Releases GPT-5"
    assert first["url"] == "https://example.com/gpt5"
    assert first["score"] == 9.2
    assert first["source_label"] == "TechCrunch"
    assert first["source_type"] == "rss"
    assert first["tags"] == ["AI", "OpenAI", "GPT-5"]
    assert len(first["images"]) == 1
    assert len(first["references"]) == 1


def test_structured_data_english():
    """English output uses English fields from metadata."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "en", "morning")

    assert data["language"] == "en"
    # First item: title falls back to title_en via title_en metadata
    # But title field uses title_{language} first, which is title_en
    first = data["items"][0]
    assert first["whats_new"] == "OpenAI released GPT-5 today."
    assert first["background"] == "GPT-5 is the fifth generation LLM."

    # Second item has community_discussion_en
    second = data["items"][1]
    assert second["community_discussion"] == "Open-source community is excited."


def test_structured_data_empty():
    """Empty items list produces valid structure."""
    s = DailySummarizer()
    data = s.get_structured_data([], "2026-06-01", 100, "zh", "morning")

    assert data["selected_count"] == 0
    assert data["items"] == []


def test_structured_data_evening():
    """Evening period produces correct labels."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "evening")

    assert data["period"] == "evening"
    assert data["next_update"] == "明早 08:00"


# --- DailyRenderer tests ---


def test_render_html_doctype():
    """Generated HTML has correct doctype and charset."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    assert "<!DOCTYPE html>" in html
    assert 'charset="UTF-8"' in html


def test_render_html_noindex():
    """Every rendered page includes robots noindex meta."""
    s = DailySummarizer()
    items = make_sample_items()
    r = DailyRenderer()

    for lang in ("zh", "en"):
        data = s.get_structured_data(items, "2026-06-01", 50, lang, "morning")
        html = r.render_html(data)
        assert 'name="robots" content="noindex, nofollow"' in html


def test_render_html_bilingual():
    """Both zh and en render without errors and contain correct labels."""
    s = DailySummarizer()
    items = make_sample_items()
    r = DailyRenderer()

    data_zh = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    html_zh = r.render_html(data_zh)
    assert "发生了什么" in html_zh
    assert "为什么重要" in html_zh
    assert "Daily Focus 早报" in html_zh

    data_en = s.get_structured_data(items, "2026-06-01", 50, "en", "evening")
    html_en = r.render_html(data_en)
    assert "What's New" in html_en
    assert "Why It Matters" in html_en
    assert "Daily Focus Evening" in html_en


def test_render_html_manifest_link():
    """HTML includes link to manifest.json."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    assert 'href="manifest.json"' in html


def test_render_html_images():
    """Images are rendered with lazy loading."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    assert 'loading="lazy"' in html
    assert "img.png" in html


def test_render_html_background_details():
    """Background section uses <details> element."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    assert "<details>" in html
    assert "背景知识" in html


def test_render_html_empty():
    """Empty items render a 'no content' empty state message."""
    r = DailyRenderer()
    data = {
        "date": "2026-06-01",
        "period": "morning",
        "language": "zh",
        "total_fetched": 100,
        "selected_count": 0,
        "next_update": "今晚 20:00",
        "items": [],
    }
    html = r.render_html(data)
    assert "今日暂无重要动态" in html


def test_render_archive():
    """Archive page renders with grouped entries."""
    r = DailyRenderer()
    entries = [
        {"date": "2026-06-01", "period_label": "早报", "title": "D1", "url": "a.html"},
        {"date": "2026-05-31", "period_label": "晚报", "title": "D2", "url": "b.html"},
    ]
    html = r.render_archive(entries)
    assert "2026-06-01" in html
    assert "2026-05-31" in html
    assert "存档" in html


def test_render_archive_empty():
    """Empty archive renders a no-content message."""
    r = DailyRenderer()
    html = r.render_archive([])
    assert "No reports yet" in html


def test_render_index():
    """Index page auto-redirects to latest_url."""
    r = DailyRenderer()
    html = r.render_index("daily/2026-06-01-morning.html")
    assert 'http-equiv="refresh"' in html
    assert "daily/2026-06-01-morning.html" in html


def test_render_html_score_colors():
    """Score badge CSS class reflects score value."""
    s = DailySummarizer()
    items = make_sample_items()
    r = DailyRenderer()

    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    html = r.render_html(data)

    # 9.2 score → score-9 class (red)
    assert 'score-9' in html


def test_structured_data_field_types():
    """Every required field in the structured data has the correct type."""
    s = DailySummarizer()
    items = make_sample_items()

    for lang in ("zh", "en"):
        for period in ("morning", "evening"):
            data = s.get_structured_data(items, "2026-06-01", 50, lang, period)

            # Top-level types
            assert isinstance(data["date"], str)
            assert data["period"] in ("morning", "evening")
            assert data["language"] in ("zh", "en")
            assert isinstance(data["total_fetched"], int)
            assert isinstance(data["selected_count"], int)
            assert isinstance(data["next_update"], str)
            assert isinstance(data["items"], list)

            # Item-level types
            for item in data["items"]:
                assert isinstance(item["index"], int)
                assert isinstance(item["title"], str)
                assert isinstance(item["title_en"], str)
                assert isinstance(item["url"], str)
                assert isinstance(item["score"], (int, float))
                assert isinstance(item["source_label"], str)
                assert isinstance(item["source_type"], str)
                assert isinstance(item["published_at"], str)
                assert isinstance(item["whats_new"], str)
                assert isinstance(item["why_it_matters"], str)
                assert isinstance(item["key_details"], str)
                assert isinstance(item["background"], str)
                assert isinstance(item["community_discussion"], str)
                assert isinstance(item["tags"], list)
                assert isinstance(item["images"], list)
                assert isinstance(item["references"], list)

                # Numeric bounds
                assert 0 <= item["score"] <= 10


def test_render_html_all_items_present():
    """All items appear in the rendered HTML."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    # Check each item title appears in the output
    assert "OpenAI 正式发布 GPT-5" in html
    assert "DeepSeek 发布 V4" in html
    # Check items in order
    assert html.index("OpenAI 正式发布 GPT-5") < html.index("DeepSeek 发布 V4")


def test_render_html_dark_mode_css():
    """Dark mode CSS variables present in <style> tag."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    assert "prefers-color-scheme: dark" in html
    assert "--bg: #0f172a" in html
    assert "--card-bg: #1e293b" in html
    assert "--text: #e2e8f0" in html
    assert "--text-secondary: #94a3b8" in html
    assert "--border: #334155" in html


def test_render_html_single_item():
    """Rendering with a single item does not crash."""
    s = DailySummarizer()
    items = make_single_item_no_optional()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    assert data["selected_count"] == 1
    assert "Sparse Item" in html
    assert "article" in html.lower() or "news-card" in html


def test_render_html_missing_optional_fields():
    """Items missing optional fields (no tags, no images, no discussion) render without error."""
    s = DailySummarizer()
    items = make_single_item_no_optional()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")

    item = data["items"][0]
    assert item["tags"] == []
    assert item["images"] == []
    assert item["community_discussion"] == ""
    assert item["background"] == ""

    r = DailyRenderer()
    html = r.render_html(data)
    assert "Sparse Item" in html
    # Should not contain community_discussion section
    assert "社区讨论" not in html
    assert "Community Discussion" not in html


def test_render_html_very_long_title():
    """Very long title (200+ chars) renders without breaking layout."""
    s = DailySummarizer()
    items = make_very_long_title_item()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    # Title should be present somewhere (not truncated or escaped away)
    assert "非常长" in html or "long title" in html.lower()
    # HTML should be structurally valid (DOCTYPE present)
    assert "<!DOCTYPE html>" in html


def test_render_html_period_titles():
    """Title includes '早报' for morning, '晚报' for evening in both languages."""
    s = DailySummarizer()
    items = make_sample_items()
    r = DailyRenderer()

    # Morning ZH
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    assert "Daily Focus 早报" in r.render_html(data)

    # Morning EN
    data = s.get_structured_data(items, "2026-06-01", 50, "en", "morning")
    assert "Daily Focus Morning" in r.render_html(data)

    # Evening ZH
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "evening")
    assert "Daily Focus 晚报" in r.render_html(data)

    # Evening EN
    data = s.get_structured_data(items, "2026-06-01", 50, "en", "evening")
    assert "Daily Focus Evening" in r.render_html(data)


# --- PWA / Static file validation ---


def test_manifest_json_valid():
    """docs/manifest.json is valid JSON with required fields."""
    manifest_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "manifest.json"
    )
    import json as json_mod
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json_mod.load(f)

    assert isinstance(manifest, dict)
    assert "name" in manifest
    assert "short_name" in manifest
    assert "start_url" in manifest
    assert "display" in manifest
    assert "theme_color" in manifest
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "index.html"
    assert isinstance(manifest.get("icons"), list)
    assert len(manifest["icons"]) >= 1


def test_robots_txt_disallow():
    """docs/robots.txt contains Disallow: /."""
    robots_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "robots.txt"
    )
    with open(robots_path, encoding="utf-8") as f:
        content = f.read()

    assert "User-agent:" in content
    assert "Disallow: /" in content


def test_sw_js_syntax():
    """docs/sw.js is a syntactically valid JavaScript file with basic structure."""
    sw_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "sw.js"
    )
    with open(sw_path, encoding="utf-8") as f:
        content = f.read()

    # Check basic structural elements
    assert "self.addEventListener" in content
    assert '"install"' in content or "'install'" in content
    assert '"activate"' in content or "'activate'" in content
    assert '"fetch"' in content or "'fetch'" in content
    assert "CACHE" in content or "cache" in content
    assert "caches.open" in content
    assert "caches.match" in content
    assert "skipWaiting" in content
    assert "clients.claim" in content


# --- Responsive design code checks ---


def test_html_max_width_and_font_stack():
    """Generated HTML includes max-width 680px and correct font stack."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    # max-width 680px
    assert "max-width: 680px" in html or "max-width:680px" in html

    # Font stack includes PingFang SC
    assert "PingFang SC" in html
    assert "Hiragino Sans GB" in html
    assert "Noto Sans SC" in html
    assert "Microsoft YaHei" in html


def test_html_card_styling():
    """News cards have border, rounded corners, and pill/badge tag style."""
    s = DailySummarizer()
    items = make_sample_items()
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")
    r = DailyRenderer()
    html = r.render_html(data)

    # Cards: border + rounded corners
    assert "border-radius: 12px" in html or "border-radius:12px" in html
    assert "border: 1px solid" in html or "border:1px solid" in html

    # Tags: pill/badge style (border-radius: 100px = full pill)
    assert "border-radius: 100px" in html or "border-radius:100px" in html
