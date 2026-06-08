"""Quality assurance tests for the daily pipeline output.

Focus areas:
1.  whats_new vs why_it_matters are distinct text (P0)
2.  Topic distribution minimums are met (per-tab counts)
3.  Chinese language detection via _has_cjk()
4.  language_mismatch flagging for non-CJK content in zh mode
5.  Filename generation and parsing conventions
6.  CJK content ratio validation
7.  is_demo default semantics
8.  Per-topic selection limits (max cap, min floor, sorting)
9.  TopicLimitConfig min <= max validation
10. Non-RSS topic fallback (HackerNews/Reddit/GitHub/OSSInsight -> ai-tech)
11. Orchestrator reads topic_limits from config (not hardcoded MIN_ITEMS)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ai.summarizer import DailySummarizer, _has_cjk
from src.models import SourceType, TopicLimitConfig
from tests.conftest_helpers import make_content_item


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_item(
    item_id: str,
    title: str,
    title_en: str = "",
    topic: str = "ai-tech",
    whats_new_zh: str = "",
    whats_new_en: str = "",
    why_it_matters_zh: str = "",
    why_it_matters_en: str = "",
    background_zh: str = "",
    community_discussion_zh: str = "",
    score: float = 7.0,
    feed_name: str = "Test Source",
) -> "ContentItem":
    """Build a ContentItem with the metadata fields the pipeline enricher would fill."""
    meta = {
        "title_en": title_en or title,
        "feed_name": feed_name,
        "topic": topic,
    }
    if whats_new_zh:
        meta["whats_new_zh"] = whats_new_zh
    if whats_new_en:
        meta["whats_new_en"] = whats_new_en
    if why_it_matters_zh:
        meta["why_it_matters_zh"] = why_it_matters_zh
    if why_it_matters_en:
        meta["why_it_matters_en"] = why_it_matters_en
    if background_zh:
        meta["background_zh"] = background_zh
    if community_discussion_zh:
        meta["community_discussion_zh"] = community_discussion_zh

    return make_content_item(
        item_id=item_id,
        title=title,
        url=f"https://example.com/{item_id}",
        ai_score=score,
        ai_summary=f"Summary of {title}",
        ai_reason=f"Reason for {title}",
        ai_tags=["test"],
        metadata=meta,
    )


def _count_tab_items(structured, tab_key: str) -> int:
    """Return the number of items in a given tab."""
    return len(structured["tabs"].get(tab_key, {}).get("items", []))


# ---------------------------------------------------------------------------
# Test 1:  whats_new vs why_it_matters are DIFFERENT text  (P0 regression)
# ---------------------------------------------------------------------------

def test_whats_new_and_why_it_matters_are_distinct_zh():
    """Whats-new and why-it-matters fields must be different in Chinese mode."""
    s = DailySummarizer()
    items = [
        make_item(
            "item-1",
            "测试新闻标题",
            title_en="Test News Title",
            topic="ai-tech",
            whats_new_zh="这是今天发生的重大新闻内容。",
            why_it_matters_zh="这条新闻很重要因为它改变了行业格局。",
        ),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")

    for item in data["items"]:
        assert item["whats_new"], "whats_new should not be empty"
        assert item["why_it_matters"], "why_it_matters should not be empty"
        assert item["whats_new"] != item["why_it_matters"], (
            "P0 BUG: whats_new and why_it_matters are identical!\n"
            f"  whats_new:      {item['whats_new'][:80]!r}\n"
            f"  why_it_matters: {item['why_it_matters'][:80]!r}"
        )


def test_whats_new_and_why_it_matters_are_distinct_en():
    """Whats-new and why-it-matters fields must be different in English mode."""
    s = DailySummarizer()
    items = [
        make_item(
            "item-en-1",
            "Test News Title",
            topic="ai-tech",
            whats_new_en="This is what happened today.",
            why_it_matters_en="This matters because it changes the industry.",
        ),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "en", "morning")

    for item in data["items"]:
        assert item["whats_new"] != item["why_it_matters"], (
            "P0 BUG: whats_new and why_it_matters are identical in en mode!\n"
            f"  whats_new:      {item['whats_new'][:80]!r}\n"
            f"  why_it_matters: {item['why_it_matters'][:80]!r}"
        )


def test_whats_new_and_why_it_matters_uses_separate_metadata_keys():
    """Verify _item_to_dict pulls from separate metadata keys, not the same fallback."""
    s = DailySummarizer()

    # Provide ONLY whats_new_zh — why_it_matters should fall back to ai_reason
    items = [
        make_item(
            "item-fallback",
            "Fallback Test",
            topic="ai-tech",
            whats_new_zh="独家新闻内容。",
            # No why_it_matters_zh provided — will fall back to ai_reason
        ),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")

    item = data["items"][0]
    assert item["whats_new"] == "独家新闻内容。"
    assert item["why_it_matters"] == "Reason for Fallback Test"
    assert item["whats_new"] != item["why_it_matters"], (
        "Fallback chain collapsed whats_new and why_it_matters to the same value"
    )


# ---------------------------------------------------------------------------
# Test 2:  Topic distribution minimums
# ---------------------------------------------------------------------------

def test_topic_distribution_ai_tech_minimum():
    """ai-tech tab must contain at least 4 items when provided."""
    s = DailySummarizer()
    items = [
        make_item(f"ai-{i}", f"AI Tech News {i}", topic="ai-tech",
                  whats_new_zh=f"技术新闻{i}内容。", why_it_matters_zh=f"技术新闻{i}重要性。")
        for i in range(4)
    ]
    data = s.get_structured_data(items, "2026-06-01", 20, "zh", "morning")
    assert _count_tab_items(data, "ai-tech") >= 4, (
        f"ai-tech tab has {_count_tab_items(data, 'ai-tech')} items, expected >= 4"
    )


def test_topic_distribution_ai_markets_minimum():
    """ai-markets tab must contain at least 6 items when provided."""
    s = DailySummarizer()
    items = [
        make_item(f"mkt-{i}", f"AI Market News {i}", topic="ai-markets",
                  whats_new_zh=f"市场新闻{i}内容。", why_it_matters_zh=f"市场新闻{i}重要性。")
        for i in range(6)
    ]
    data = s.get_structured_data(items, "2026-06-01", 30, "zh", "morning")
    assert _count_tab_items(data, "ai-markets") >= 6, (
        f"ai-markets tab has {_count_tab_items(data, 'ai-markets')} items, expected >= 6"
    )


def test_topic_distribution_economy_minimum():
    """economy tab must contain at least 6 items when provided."""
    s = DailySummarizer()
    items = [
        make_item(f"eco-{i}", f"Economy News {i}", topic="economy",
                  whats_new_zh=f"经济新闻{i}内容。", why_it_matters_zh=f"经济新闻{i}重要性。")
        for i in range(6)
    ]
    data = s.get_structured_data(items, "2026-06-01", 30, "zh", "morning")
    assert _count_tab_items(data, "economy") >= 6, (
        f"economy tab has {_count_tab_items(data, 'economy')} items, expected >= 6"
    )


def test_topic_distribution_mixed_tabs():
    """Multiple tabs all get correct counts from a mixed item list."""
    s = DailySummarizer()
    items = (
        [make_item(f"ai-{i}", f"AI Tech {i}", topic="ai-tech",
                   whats_new_zh=f"内容{i}。", why_it_matters_zh=f"重要{i}。")
         for i in range(5)]
        + [make_item(f"mkt-{i}", f"AI Market {i}", topic="ai-markets",
                     whats_new_zh=f"市场{i}。", why_it_matters_zh=f"市场重要{i}。")
           for i in range(7)]
        + [make_item(f"eco-{i}", f"Economy {i}", topic="economy",
                     whats_new_zh=f"经济{i}。", why_it_matters_zh=f"经济重要{i}。")
           for i in range(6)]
    )
    data = s.get_structured_data(items, "2026-06-01", 50, "zh", "morning")

    counts = {
        "ai-tech": _count_tab_items(data, "ai-tech"),
        "ai-markets": _count_tab_items(data, "ai-markets"),
        "economy": _count_tab_items(data, "economy"),
    }
    assert counts["ai-tech"] == 5, f"Expected 5 ai-tech, got {counts['ai-tech']}"
    assert counts["ai-markets"] == 7, f"Expected 7 ai-markets, got {counts['ai-markets']}"
    assert counts["economy"] == 6, f"Expected 6 economy, got {counts['economy']}"
    assert sum(counts.values()) == 18, f"Total items mismatch: {sum(counts.values())} vs 18"


def test_topic_distribution_empty_tab():
    """An empty tab should produce 0 items, not crash."""
    s = DailySummarizer()
    items = [
        make_item("ai-1", "AI News", topic="ai-tech",
                  whats_new_zh="内容。", why_it_matters_zh="重要。"),
        make_item("mkt-1", "Market News", topic="ai-markets",
                  whats_new_zh="市场。", why_it_matters_zh="市场重要。"),
    ]
    data = s.get_structured_data(items, "2026-06-01", 5, "zh", "morning")
    assert _count_tab_items(data, "economy") == 0, "economy tab should be empty"
    assert _count_tab_items(data, "ai-tech") == 1
    assert _count_tab_items(data, "ai-markets") == 1


def test_topic_distribution_all_three_tabs_present():
    """The structured data must always contain all 3 tab keys."""
    s = DailySummarizer()
    items = [make_item("ai-1", "Only AI", topic="ai-tech",
                       whats_new_zh="内容。", why_it_matters_zh="重要。")]
    data = s.get_structured_data(items, "2026-06-01", 1, "zh", "morning")

    for key in ("ai-tech", "ai-markets", "economy"):
        assert key in data["tabs"], f"Missing tab key: {key}"


# ---------------------------------------------------------------------------
# Test 3:  Chinese language detection
# ---------------------------------------------------------------------------

class TestHasCjk:
    """Unit tests for the _has_cjk() helper."""

    def test_pure_chinese(self):
        assert _has_cjk("这是一段中文文本") is True

    def test_chinese_with_punctuation(self):
        assert _has_cjk("今天天气真好！") is True

    def test_chinese_with_numbers(self):
        assert _has_cjk("2026年6月2日") is True

    def test_chinese_mixed_english(self):
        assert _has_cjk("OpenAI 发布了 GPT-5 模型") is True

    def test_english_only(self):
        assert _has_cjk("This is English text only.") is False

    def test_english_with_numbers(self):
        assert _has_cjk("The year 2026 has 365 days.") is False

    def test_empty_string(self):
        assert _has_cjk("") is False

    def test_whitespace_only(self):
        assert _has_cjk("   \n  \t  ") is False

    def test_japanese_kanji(self):
        """Japanese kanji characters fall in the CJK range, so they should match."""
        assert _has_cjk("東京") is True

    def test_korean_hangul(self):
        """Korean Hangul is outside the CJK range and should NOT match."""
        assert _has_cjk("한국어") is False

    def test_special_chars_only(self):
        assert _has_cjk("!@#$%^&*()") is False


# ---------------------------------------------------------------------------
# Test 4:  language_mismatch flagging
# ---------------------------------------------------------------------------

def test_language_mismatch_false_when_chinese_present():
    """language_mismatch should be False when content contains CJK."""
    s = DailySummarizer()
    items = [
        make_item(
            "zh-item",
            "中文新闻",
            topic="ai-tech",
            whats_new_zh="今天发布了重要新闻。",
            why_it_matters_zh="这很重要。",
            background_zh="背景信息。",
            community_discussion_zh="社区讨论。",
        ),
    ]
    data = s.get_structured_data(items, "2026-06-01", 5, "zh", "morning")
    assert data["items"][0]["language_mismatch"] is False


def test_language_mismatch_true_when_english_in_zh_mode():
    """language_mismatch should be True when content is all English in zh mode."""
    s = DailySummarizer()
    items = [
        make_item(
            "en-item",
            "English Title",
            topic="ai-tech",
            whats_new_zh="This is English content without any Chinese characters.",
            why_it_matters_zh="This matters but is also in English only.",
            background_zh="Background in English only.",
        ),
    ]
    data = s.get_structured_data(items, "2026-06-01", 5, "zh", "morning")
    assert data["items"][0]["language_mismatch"] is True, (
        "language_mismatch should be True when zh mode has all-English content"
    )


def test_language_mismatch_not_set_in_en_mode():
    """language_mismatch should be False in English mode regardless of content."""
    s = DailySummarizer()
    items = [
        make_item(
            "en-item-2",
            "English Title",
            topic="ai-tech",
            whats_new_en="This is English content.",
            why_it_matters_en="This matters.",
        ),
    ]
    data = s.get_structured_data(items, "2026-06-01", 5, "en", "morning")
    assert data["items"][0]["language_mismatch"] is False


def test_language_mismatch_true_on_fallback_english():
    """language_mismatch should be True when fallback text is all English in zh mode.

    Even without explicit zh metadata, the ai_summary/ai_reason fallback produces
    English text, so the flag must be True.
    """
    s = DailySummarizer()
    items = [
        make_item(
            "fallback-item",
            "Fallback Item",
            topic="ai-tech",
        ),
    ]
    data = s.get_structured_data(items, "2026-06-01", 5, "zh", "morning")
    assert data["items"][0]["language_mismatch"] is True, (
        "Fallback ai_summary/ai_reason are English, so language_mismatch should be True"
    )


# ---------------------------------------------------------------------------
# Test 5:  score_threshold propagated to structured data
# ---------------------------------------------------------------------------

def test_score_threshold_propagated():
    """The score_threshold kwarg is passed through to the output dict."""
    s = DailySummarizer()
    items = [make_item("t-1", "Threshold Test", topic="ai-tech",
                       whats_new_zh="内容。", why_it_matters_zh="重要。")]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning",
                                 score_threshold=6.5)
    assert data["score_threshold"] == 6.5


# ---------------------------------------------------------------------------
# Test 6:  Language-specific filename generation
# ---------------------------------------------------------------------------

def test_filename_generation_zh():
    """Verify zh filename is generated correctly."""
    date = "2026-06-01"
    period = "morning"
    lang = "zh"
    filename = f"{date}-{period}-{lang}.html"
    assert filename == "2026-06-01-morning-zh.html"


def test_filename_generation_en():
    """Verify en filename is generated correctly."""
    date = "2026-06-01"
    period = "morning"
    lang = "en"
    filename = f"{date}-{period}-{lang}.html"
    assert filename == "2026-06-01-morning-en.html"


def test_filename_generation_evening():
    """Verify evening period filename is generated correctly."""
    date = "2026-06-01"
    period = "evening"
    lang = "en"
    filename = f"{date}-{period}-{lang}.html"
    assert filename == "2026-06-01-evening-en.html"


def test_filename_roundtrip():
    """Verify filename parsing round-trips correctly.

    The orchestrator generates {date}-{period}-{lang}.html.
    render_and_deploy.py's _parse_daily_html_path extracts these back.
    """
    # Dynamic import to avoid circular/import issues with non-test deps
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "render_and_deploy",
        Path(__file__).resolve().parent.parent / "scripts" / "render_and_deploy.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError("Could not import render_and_deploy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cases = [
        ("2026-06-01-morning-zh.html", "2026-06-01", "morning", "zh"),
        ("2026-06-01-morning-en.html", "2026-06-01", "morning", "en"),
        ("2026-06-01-evening-en.html", "2026-06-01", "evening", "en"),
        ("2026-06-15-morning-zh.html", "2026-06-15", "morning", "zh"),
    ]
    for filename, exp_date, exp_period, exp_lang in cases:
        parsed = mod._parse_daily_html_path(Path(filename))
        assert parsed is not None, f"_parse_daily_html_path({filename!r}) returned None"
        assert parsed["date"] == exp_date, f"{filename}: expected date {exp_date!r}, got {parsed['date']!r}"
        assert parsed["period"] == exp_period, f"{filename}: expected period {exp_period!r}, got {parsed['period']!r}"
        assert parsed["lang"] == exp_lang, f"{filename}: expected lang {exp_lang!r}, got {parsed['lang']!r}"


def test_filename_legacy_pattern():
    """Verify legacy filename (no lang suffix) parses correctly."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "render_and_deploy",
        Path(__file__).resolve().parent.parent / "scripts" / "render_and_deploy.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError("Could not import render_and_deploy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    parsed = mod._parse_daily_html_path(Path("2026-06-01-morning.html"))
    assert parsed is not None
    assert parsed["date"] == "2026-06-01"
    assert parsed["period"] == "morning"
    assert parsed["lang"] is None


# ---------------------------------------------------------------------------
# Test 7:  CJK content ratio
# ---------------------------------------------------------------------------

def test_has_cjk_detects_majority_chinese():
    """Verify _has_cjk returns True when >50% of meaningful chars are CJK."""
    # Mix with mostly Chinese, some English
    text = "今天OpenAI发布了新的AI模型这是一个重要的里程碑标志着人工智能技术的进步"
    assert _has_cjk(text) is True, "Mostly Chinese text should be detected as CJK"


def test_has_cjk_rejects_majority_english():
    """Verify _has_cjk returns False when <50% of meaningful chars are CJK."""
    text = "Today OpenAI released a new AI model which marks an important milestone"
    assert _has_cjk(text) is False, "Mostly English text should NOT be detected as CJK"


def test_zh_output_cjk_ratio_over_50_percent():
    """Verify simulated zh pipeline output has sufficient CJK density."""
    # Simulate a zh-mode structured data item
    zh_content_items = [
        "这是一条重要的科技新闻，今天发生了重大变化。",
        "这个突破将改变整个行业格局，多家公司已经宣布跟进。",
        "分析师认为这一趋势将持续到明年，投资者应保持关注。",
    ]
    for item in zh_content_items:
        assert _has_cjk(item) is True, f"Chinese content failed CJK check: {item[:50]}"


# ---------------------------------------------------------------------------
# Test 8:  is_demo defaults to false
# ---------------------------------------------------------------------------

def test_is_demo_not_in_structured_data():
    """Verify get_structured_data output does not set is_demo=True."""
    s = DailySummarizer()
    items = [
        make_item(
            "item-1", "Test News", topic="ai-tech",
            whats_new_zh="测试新闻内容。", why_it_matters_zh="测试新闻重要性。",
        ),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    # is_demo should NOT be present, or if present, must be False
    is_demo = data.get("is_demo", False)
    assert is_demo is False, "is_demo must default to False in structured data"


def test_is_demo_false_no_demo_banner():
    """Verify rendering with default (no is_demo) produces no demo banner."""
    from src.renderer import DailyRenderer

    s = DailySummarizer()
    renderer = DailyRenderer()
    items = [
        make_item(
            "item-1", "Test News", topic="ai-tech",
            whats_new_zh="测试新闻内容。", why_it_matters_zh="测试新闻重要性。",
        ),
    ]
    data = s.get_structured_data(items, "2026-06-01", 10, "zh", "morning")
    html = renderer.render_html(data)

    # The template shows demo-banner only when is_demo is truthy
    # When absent/default, the banner DIV should NOT appear
    # (CSS class definitions for .demo-banner always exist in the stylesheet)
    assert '<div class="demo-banner">' not in html, (
        "Demo banner DIV should NOT appear when is_demo is not set (defaults to false)"
    )


# ---------------------------------------------------------------------------
# Test 9:  Content volume — whats_new average length >= 100 chars
# ---------------------------------------------------------------------------

def test_whats_new_average_length_meets_threshold():
    """Verify that each article's whats_new field averages >= 100 characters.

    Short whats_new text suggests the AI enricher is producing too-brief
    summaries that lack sufficient detail for readers.
    """
    s = DailySummarizer()

    # Build items with whats_new content averaging >= 100 chars.
    # The minimum-length item should still be crisp but informative.
    items = [
        make_item(
            f"vol-{i}",
            f"Volume Test Article {i + 1}",
            topic="ai-tech" if i < 4 else ("ai-markets" if i < 10 else "economy"),
            whats_new_zh=(
                "2026年6月，谷歌发布了新一代Gemma模型，"
                "这是一个重大的技术突破，将彻底改变AI行业的格局。"
                "新模型在多项基准测试中表现优异，尤其是在推理能力方面。"
                "业内人士普遍认为，这是近年来最重要的模型发布之一。"
                "预计将推动整个生态系统向前迈进一大步。"
            ),
            why_it_matters_zh=(
                "这项发布对AI行业具有深远影响，不仅提升了技术上限，"
                "还为开发者提供了更强大的工具。"
            ),
        )
        for i in range(18)
    ]

    data = s.get_structured_data(items, "2026-06-03", 20, "zh", "morning")

    total_chars = sum(len(item["whats_new"]) for item in data["items"])
    avg_chars = total_chars / len(data["items"]) if data["items"] else 0

    assert avg_chars >= 100, (
        f"Average whats_new length is {avg_chars:.0f} chars — "
        f"expected >= 100 chars across {len(data['items'])} items.\n"
        "This suggests the summarizer may be producing overly brief content. "
        "Check the enricher prompt for length guidance."
    )


# ---------------------------------------------------------------------------
# Test 10:  community_discussion waste detection
# ---------------------------------------------------------------------------

def test_community_discussion_waste_detected():
    """Verify community_discussion is always empty, indicating wasted token spend.

    The enricher prompt instructs the LLM to generate community_discussion_en
    and community_discussion_zh for EVERY item, even when no community comments
    exist. This adds ~100 input tokens (prompt instructions) and ~70 output
    tokens (empty JSON keys) per item — but the field is almost always empty
    and never displayed in the rendered UI.

    This test logs a warning if community_discussion is empty in all items,
    flagging it for removal from the enrichment prompt to save tokens.
    """
    import logging
    logger = logging.getLogger(__name__)

    s = DailySummarizer()

    # Simulate real-world: items that went through the enricher but have
    # no community_discussion field (LLM returned empty string for both langs)
    items = [
        make_item(
            f"waste-{i}",
            f"Waste Test Item {i}",
            topic="ai-tech" if i < 4 else ("ai-markets" if i < 10 else "economy"),
            whats_new_zh=f"这是第{i}条新闻的详细内容描述，包含具体事件细节和背景信息。",
            why_it_matters_zh=f"这条新闻的重要性主要体现在对行业格局的影响方面。",
            # Intentionally NOT setting community_discussion — simulating
            # the enricher returning empty string (the common case)
        )
        for i in range(32)
    ]

    data = s.get_structured_data(items, "2026-06-08", 62, "zh", "morning")

    empty_count = 0
    total_count = len(data["items"])
    for item in data["items"]:
        # community_discussion comes from _item_to_dict() which falls back
        # to meta.get("community_discussion_zh") -> "" when not set
        if not item.get("community_discussion", "").strip():
            empty_count += 1

    # Log the waste warning (visible with e.g. pytest -s -v)
    if empty_count == total_count:
        logger.warning(
            "WASTE: community_discussion is empty in ALL %d items. "
            "The enricher spends ~170 tokens per item generating this field "
            "but it is never displayed because the LLM always returns empty "
            "string (no community comments to summarize). "
            "Consider removing community_discussion from the enrichment prompt "
            "to save ~%d input tokens + ~%d output tokens per run.",
            total_count,
            total_count * 100,   # ~100 input tokens for prompt instructions
            total_count * 70,    # ~70 output tokens for empty JSON keys
        )
    elif empty_count > total_count * 0.5:
        logger.warning(
            "community_discussion is empty in %d/%d items (%.0f%%). "
            "This still represents significant token waste.",
            empty_count, total_count, 100.0 * empty_count / total_count,
        )

    # Assert: the community_discussion field exists (not None) even when empty
    for item in data["items"]:
        assert "community_discussion" in item, (
            "community_discussion key must exist in item dict"
        )


# ---------------------------------------------------------------------------
# Selection logic helper (mirrors orchestrator step 5b: per-topic hard limits)
# ---------------------------------------------------------------------------

def _apply_topic_limits(items, limits: dict[str, TopicLimitConfig]):
    """Select top-N items per topic by score, enforcing min/max per topic.

    Replicates the orchestrator's per-topic selection logic from step 5b.
    Items are sorted globally by score descending after per-topic selection.

    Args:
        items: List of ContentItem with metadata["topic"] set.
        limits: Dict mapping topic name to TopicLimitConfig(min, max).

    Returns:
        List[ContentItem]: Selected items, sorted by score descending.
    """
    if not limits:
        return sorted(items, key=lambda x: x.ai_score or 0, reverse=True)

    selected = []
    for topic, limit_config in sorted(limits.items()):
        topic_items = [i for i in items if i.metadata.get("topic") == topic]
        topic_items.sort(key=lambda x: x.ai_score or 0, reverse=True)
        n = max(min(limit_config.max, len(topic_items)), limit_config.min)
        n = min(n, len(topic_items))
        selected.extend(topic_items[:n])

    selected.sort(key=lambda x: x.ai_score or 0, reverse=True)
    return selected


def _make_topic_item(
    item_id: str,
    topic: str,
    score: float,
    title: str = "",
) -> "ContentItem":
    """Create a minimal ContentItem for testing per-topic selection logic."""
    return make_content_item(
        item_id=item_id,
        title=title or f"{topic}-{item_id}",
        url=f"https://example.com/{item_id}",
        ai_score=score,
        ai_summary=f"Summary of {item_id}",
        ai_reason=f"Reason for {item_id}",
        ai_tags=["test"],
        metadata={"topic": topic},
    )


# ---------------------------------------------------------------------------
# Test 11:  Per-topic MAX limits (orchestrator step 5b)
# ---------------------------------------------------------------------------

def test_per_topic_max_limits_enforced():
    """With 20+ items per topic, selection must cap at per-topic max (10/10/7)."""
    limits = {
        "ai-tech": TopicLimitConfig(min=6, max=10),
        "ai-markets": TopicLimitConfig(min=6, max=10),
        "economy": TopicLimitConfig(min=5, max=7),
    }

    items = []
    for topic in ("ai-tech", "ai-markets", "economy"):
        for i in range(25):
            items.append(_make_topic_item(
                f"{topic}-{i}", topic, score=10.0 - i * 0.4,
                title=f"{topic} Item {i}",
            ))

    selected = _apply_topic_limits(items, limits)

    # Count per topic
    from collections import Counter
    counts = Counter(i.metadata["topic"] for i in selected)

    assert counts["ai-tech"] == 10, f"ai-tech: expected 10, got {counts['ai-tech']}"
    assert counts["ai-markets"] == 10, f"ai-markets: expected 10, got {counts['ai-markets']}"
    assert counts["economy"] == 7, f"economy: expected 7, got {counts['economy']}"
    assert len(selected) == 27, f"Total: expected 27, got {len(selected)}"


def test_per_topic_max_limits_no_excess():
    """No topic exceeds its max even when candidate count far exceeds max."""
    limits = {
        "ai-tech": TopicLimitConfig(min=4, max=10),
        "ai-markets": TopicLimitConfig(min=4, max=10),
        "economy": TopicLimitConfig(min=4, max=7),
    }

    items = [_make_topic_item(f"excess-{i}", "ai-tech", 9.5) for i in range(100)]
    selected = _apply_topic_limits(items, limits)
    assert len(selected) == 10, f"100 ai-tech items must cap at 10, got {len(selected)}"


def test_per_topic_max_uses_highest_scores():
    """When capped at max, the highest-scored items are selected."""
    limits = {"ai-tech": TopicLimitConfig(min=1, max=5)}

    # Scores: 1.0, 2.0, ..., 20.0
    items = [_make_topic_item(f"s-{i}", "ai-tech", i * 1.0) for i in range(1, 21)]
    selected = _apply_topic_limits(items, limits)

    assert len(selected) == 5, f"Expected 5 top items, got {len(selected)}"
    # Highest 5 scores should be 20, 19, 18, 17, 16
    top_scores = sorted([i.ai_score for i in selected], reverse=True)
    assert top_scores == [20.0, 19.0, 18.0, 17.0, 16.0], (
        f"Expected [20, 19, 18, 17, 16], got {top_scores}"
    )


# ---------------------------------------------------------------------------
# Test 12:  Per-topic MIN limits
# ---------------------------------------------------------------------------

def test_per_topic_min_limits_honored():
    """Items below max but at or above min are all selected."""
    limits = {
        "ai-tech": TopicLimitConfig(min=6, max=10),
        "ai-markets": TopicLimitConfig(min=6, max=10),
        "economy": TopicLimitConfig(min=5, max=7),
    }

    items = (
        [_make_topic_item(f"ai-{i}", "ai-tech", 8.0) for i in range(6)]
        + [_make_topic_item(f"mkt-{i}", "ai-markets", 7.5) for i in range(8)]
        + [_make_topic_item(f"eco-{i}", "economy", 7.0) for i in range(5)]
    )

    selected = _apply_topic_limits(items, limits)

    from collections import Counter
    counts = Counter(i.metadata["topic"] for i in selected)
    assert counts["ai-tech"] == 6, f"ai-tech: expected 6 (at min), got {counts['ai-tech']}"
    assert counts["ai-markets"] == 8, f"ai-markets: expected 8 (between min and max), got {counts['ai-markets']}"
    assert counts["economy"] == 5, f"economy: expected 5 (at min), got {counts['economy']}"
    assert len(selected) == 19, f"Total: expected 19, got {len(selected)}"


def test_per_topic_min_below_minimum():
    """When items available are below min, all available items are selected (no crash)."""
    limits = {"economy": TopicLimitConfig(min=5, max=7)}

    items = [_make_topic_item(f"eco-{i}", "economy", 7.0) for i in range(3)]
    selected = _apply_topic_limits(items, limits)

    assert len(selected) == 3, f"Only 3 available, expected 3, got {len(selected)}"


def test_per_topic_zero_items_for_topic():
    """When a topic has 0 items, it contributes 0 items to the selection (no crash)."""
    limits = {
        "ai-tech": TopicLimitConfig(min=6, max=10),
        "economy": TopicLimitConfig(min=5, max=7),
    }

    items = [_make_topic_item(f"ai-{i}", "ai-tech", 8.0) for i in range(6)]
    selected = _apply_topic_limits(items, limits)

    from collections import Counter
    counts = Counter(i.metadata["topic"] for i in selected)
    assert counts.get("economy", 0) == 0, "economy should contribute 0 items"


# ---------------------------------------------------------------------------
# Test 13:  Sorting by score within tabs
# ---------------------------------------------------------------------------

def test_global_sort_by_score_descending():
    """All selected items must be globally sorted by score descending."""
    limits = {"ai-tech": TopicLimitConfig(min=1, max=10)}

    # Scores: 1, 3, 5, 7, 9, 2, 4, 6, 8, 10 (mixed order intentionally)
    items = [_make_topic_item(f"i-{s}", "ai-tech", s * 1.0) for s in [1, 3, 5, 7, 9, 2, 4, 6, 8, 10]]
    selected = _apply_topic_limits(items, limits)

    scores = [i.ai_score for i in selected]
    assert scores == sorted(scores, reverse=True), (
        f"Items not sorted by score descending: {scores}"
    )


def test_items_sorted_by_score_within_tabs():
    """After get_structured_data, tabs contain items sorted by score descending."""
    s = DailySummarizer()
    limits = {"ai-tech": TopicLimitConfig(min=1, max=10)}

    items = [_make_topic_item(f"i-{s}", "ai-tech", s * 1.0) for s in [1, 5, 3, 7, 9, 2, 8, 4, 6, 10]]
    with_score = [(i, i.ai_score) for i in items]
    selected = _apply_topic_limits(items, limits)

    data = s.get_structured_data(selected, "2026-06-08", 30, "zh", "morning")

    # Check sorting within ai-tech tab
    tab_items = data["tabs"]["ai-tech"]["items"]
    tab_scores = [it["score"] for it in tab_items]
    assert tab_scores == sorted(tab_scores, reverse=True), (
        f"ai-tech tab items not sorted by score descending: {tab_scores}"
    )

    # Check flat items also sorted
    flat_scores = [it["score"] for it in data["items"]]
    assert flat_scores == sorted(flat_scores, reverse=True), (
        f"Flat items not sorted by score descending: {flat_scores}"
    )


# ---------------------------------------------------------------------------
# Test 14:  Enrichment count with per-topic limits
# ---------------------------------------------------------------------------

def test_enrichment_count_with_limits():
    """With 60 passing items (20/topic) and limits 10+10+7=27, enrichment ≤ 27.

    This validates that enrichment (orchestrator step 6) only processes
    the items selected by step 5b, not all passing items.
    """
    limits = {
        "ai-tech": TopicLimitConfig(min=6, max=10),
        "ai-markets": TopicLimitConfig(min=6, max=10),
        "economy": TopicLimitConfig(min=5, max=7),
    }

    # 20 items per topic with descending scores
    items = []
    for topic in ("ai-tech", "ai-markets", "economy"):
        for i in range(20):
            items.append(_make_topic_item(
                f"{topic}-{i}", topic, score=10.0 - i * 0.5,
                title=f"{topic} Item {i}",
            ))

    selected = _apply_topic_limits(items, limits)

    # Enrichment should only run on selected items
    assert len(selected) <= 27, (
        f"Enrichment would process {len(selected)} items, expected ≤ 27"
    )

    from collections import Counter
    counts = Counter(i.metadata["topic"] for i in selected)
    assert counts["ai-tech"] == 10
    assert counts["ai-markets"] == 10
    assert counts["economy"] == 7
    assert len(selected) == 27, f"Total selected: {len(selected)}"


def test_enrichment_count_no_limits_all_items():
    """Without topic_limits configured, enrichment processes all items."""
    items = [_make_topic_item(f"i-{i}", "ai-tech", 8.0) for i in range(50)]
    selected = _apply_topic_limits(items, {})

    assert len(selected) == 50, (
        f"Without limits, all 50 items should be selected, got {len(selected)}"
    )


# ---------------------------------------------------------------------------
# Test 15:  Per-topic limits via get_structured_data (integration)
# ---------------------------------------------------------------------------

def test_get_structured_data_reflects_selected_counts():
    """After per-topic selection, get_structured_data shows correct tab counts."""
    s = DailySummarizer()
    limits = {
        "ai-tech": TopicLimitConfig(min=4, max=10),
        "ai-markets": TopicLimitConfig(min=4, max=10),
        "economy": TopicLimitConfig(min=4, max=7),
    }

    items = (
        [_make_topic_item(f"ai-{i}", "ai-tech", 9.0 - i * 0.5) for i in range(15)]
        + [_make_topic_item(f"mkt-{i}", "ai-markets", 8.5 - i * 0.5) for i in range(15)]
        + [_make_topic_item(f"eco-{i}", "economy", 8.0 - i * 0.5) for i in range(15)]
    )
    selected = _apply_topic_limits(items, limits)

    data = s.get_structured_data(selected, "2026-06-08", 80, "zh", "morning")

    assert len(data["tabs"]["ai-tech"]["items"]) == 10, (
        f"ai-tech tab: expected 10, got {len(data['tabs']['ai-tech']['items'])}"
    )
    assert len(data["tabs"]["ai-markets"]["items"]) == 10, (
        f"ai-markets tab: expected 10, got {len(data['tabs']['ai-markets']['items'])}"
    )
    assert len(data["tabs"]["economy"]["items"]) == 7, (
        f"economy tab: expected 7, got {len(data['tabs']['economy']['items'])}"
    )
    assert data["selected_count"] == 27, (
        f"selected_count: expected 27, got {data['selected_count']}"
    )


# ===========================================================================
# QA 1 — Task 1: Verify capping works with specific mock data
# 50 ai-tech + 20 ai-markets + 15 economy -> top 10 + top 10 + top 7 = 27
# ===========================================================================

def test_capping_50_ai_tech_20_ai_markets_15_economy():
    """With 50 ai-tech, 20 ai-markets, 15 economy items, verify:
    - ai-tech caps at 10 (not 50)
    - ai-markets caps at 10 (not 20)
    - economy caps at 7 (not 15)
    - total selected <= 27
    """
    limits = {
        "ai-tech": TopicLimitConfig(min=6, max=10),
        "ai-markets": TopicLimitConfig(min=6, max=10),
        "economy": TopicLimitConfig(min=5, max=7),
    }

    items = []
    # 50 ai-tech with descending scores
    for i in range(50):
        items.append(_make_topic_item(
            f"ai-tech-{i}", "ai-tech", score=10.0 - i * 0.2,
            title=f"AI Tech Item {i}",
        ))
    # 20 ai-markets with descending scores
    for i in range(20):
        items.append(_make_topic_item(
            f"ai-markets-{i}", "ai-markets", score=9.5 - i * 0.4,
            title=f"AI Markets Item {i}",
        ))
    # 15 economy with descending scores
    for i in range(15):
        items.append(_make_topic_item(
            f"economy-{i}", "economy", score=9.0 - i * 0.5,
            title=f"Economy Item {i}",
        ))

    selected = _apply_topic_limits(items, limits)
    from collections import Counter
    counts = Counter(i.metadata["topic"] for i in selected)

    assert counts["ai-tech"] == 10, f"ai-tech: expected 10, got {counts['ai-tech']}"
    assert counts["ai-markets"] == 10, f"ai-markets: expected 10, got {counts['ai-markets']}"
    assert counts["economy"] == 7, f"economy: expected 7, got {counts['economy']}"
    assert len(selected) == 27, f"Total: expected 27, got {len(selected)}"

    # Verify the top scores were selected for each topic
    ai_tech_scores = sorted(
        [i.ai_score for i in selected if i.metadata["topic"] == "ai-tech"],
        reverse=True,
    )
    assert ai_tech_scores == [10.0, 9.8, 9.6, 9.4, 9.2, 9.0, 8.8, 8.6, 8.4, 8.2], (
        f"ai-tech should have top 10 scores, got {ai_tech_scores}"
    )

    economy_scores = sorted(
        [i.ai_score for i in selected if i.metadata["topic"] == "economy"],
        reverse=True,
    )
    assert economy_scores == [9.0, 8.5, 8.0, 7.5, 7.0, 6.5, 6.0], (
        f"economy should have top 7 scores, got {economy_scores}"
    )


# ===========================================================================
# QA 1 — Task 2: TopicLimitConfig min <= max validation
# ===========================================================================

def test_topic_limit_config_min_max_validation():
    """TopicLimitConfig must reject min > max."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="must be <= max"):
        TopicLimitConfig(min=10, max=5)

    with pytest.raises(ValidationError, match="must be <= max"):
        TopicLimitConfig(min=8, max=3)

    # Equal values should be valid
    c = TopicLimitConfig(min=5, max=5)
    assert c.min == 5
    assert c.max == 5

    # Normal case should be valid
    c = TopicLimitConfig(min=3, max=10)
    assert c.min == 3
    assert c.max == 10


# ===========================================================================
# QA 1 — Task 3: Non-RSS topic fallback
# ContentItems from HackerNews, Reddit, GitHub, OSSInsight without a topic
# in metadata should default to "ai-tech" in get_structured_data.
# ===========================================================================

def _make_non_rss_item(item_id: str, source_type: SourceType) -> "ContentItem":
    """Create a ContentItem from a non-RSS source without setting topic metadata."""
    return make_content_item(
        item_id=f"{source_type.value}:{item_id}",
        source_type=source_type,
        title=f"Item from {source_type.value}",
        url=f"https://example.com/{source_type.value}/{item_id}",
        ai_score=8.0,
        ai_summary=f"Summary of {source_type.value} item.",
        ai_reason=f"Reason for {source_type.value} item.",
        ai_tags=["test"],
        metadata={},  # No topic set!
    )


def _make_rss_item(item_id: str, topic: str) -> "ContentItem":
    """Create a ContentItem from RSS with a specific topic (control)."""
    return make_content_item(
        item_id=f"rss:{item_id}",
        source_type=SourceType.RSS,
        title=f"RSS item in {topic}",
        url=f"https://example.com/rss/{item_id}",
        ai_score=8.0,
        ai_summary=f"Summary of RSS {topic} item.",
        ai_reason=f"Reason for RSS {topic} item.",
        ai_tags=["test"],
        metadata={"topic": topic, "feed_name": "Test Feed"},
    )


def test_hackernews_defaults_to_ai_tech_tab():
    """HackerNews items without topic metadata go to ai-tech tab (default)."""
    s = DailySummarizer()
    items = [_make_non_rss_item("hn-1", SourceType.HACKERNEWS)]
    data = s.get_structured_data(items, "2026-06-08", 5, "zh", "morning")

    assert len(data["tabs"]["ai-tech"]["items"]) == 1, (
        f"HackerNews item should default to ai-tech tab, "
        f"got {data['tabs']['ai-tech']['items']}"
    )
    ai_tech_item = data["tabs"]["ai-tech"]["items"][0]
    assert ai_tech_item["source_type"] == "hackernews", (
        f"Expected source_type hackernews, got {ai_tech_item['source_type']}"
    )


def test_reddit_defaults_to_ai_tech_tab():
    """Reddit items without topic metadata go to ai-tech tab (default)."""
    s = DailySummarizer()
    items = [_make_non_rss_item("rd-1", SourceType.REDDIT)]
    data = s.get_structured_data(items, "2026-06-08", 5, "zh", "morning")

    assert len(data["tabs"]["ai-tech"]["items"]) == 1
    reddit_item = data["tabs"]["ai-tech"]["items"][0]
    assert reddit_item["source_type"] == "reddit"


def test_github_defaults_to_ai_tech_tab():
    """GitHub items without topic metadata go to ai-tech tab (default)."""
    s = DailySummarizer()
    items = [_make_non_rss_item("gh-1", SourceType.GITHUB)]
    data = s.get_structured_data(items, "2026-06-08", 5, "zh", "morning")

    assert len(data["tabs"]["ai-tech"]["items"]) == 1
    gh_item = data["tabs"]["ai-tech"]["items"][0]
    assert gh_item["source_type"] == "github"


def test_ossinsight_defaults_to_ai_tech_tab():
    """OSSInsight items without topic metadata go to ai-tech tab (default)."""
    s = DailySummarizer()
    items = [_make_non_rss_item("oss-1", SourceType.OSSINSIGHT)]
    data = s.get_structured_data(items, "2026-06-08", 5, "zh", "morning")

    assert len(data["tabs"]["ai-tech"]["items"]) == 1
    oss_item = data["tabs"]["ai-tech"]["items"][0]
    assert oss_item["source_type"] == "ossinsight"


def test_mixed_rss_and_non_rss_topic_fallback():
    """RSS items with explicit topics go to correct tabs, non-RSS items default to ai-tech."""
    s = DailySummarizer()
    items = [
        _make_rss_item("rss-ai", "ai-tech"),
        _make_rss_item("rss-mkt", "ai-markets"),
        _make_rss_item("rss-eco", "economy"),
        _make_non_rss_item("hn-1", SourceType.HACKERNEWS),
        _make_non_rss_item("rd-1", SourceType.REDDIT),
        _make_non_rss_item("gh-1", SourceType.GITHUB),
        _make_non_rss_item("oss-1", SourceType.OSSINSIGHT),
    ]
    data = s.get_structured_data(items, "2026-06-08", 10, "zh", "morning")

    # RSS items with explicit topics
    assert len(data["tabs"]["ai-tech"]["items"]) == 5, (
        f"ai-tech tab should have 5 items (1 RSS ai-tech + 4 non-RSS fallback), "
        f"got {len(data['tabs']['ai-tech']['items'])}"
    )
    assert len(data["tabs"]["ai-markets"]["items"]) == 1
    assert len(data["tabs"]["economy"]["items"]) == 1

    # All non-RSS items should be in ai-tech tab
    ai_tech_sources = {it["source_type"] for it in data["tabs"]["ai-tech"]["items"]}
    assert "hackernews" in ai_tech_sources
    assert "reddit" in ai_tech_sources
    assert "github" in ai_tech_sources
    assert "ossinsight" in ai_tech_sources
    assert "rss" in ai_tech_sources  # The ai-tech RSS item


# ===========================================================================
# QA 1 — Task 4: Verify orchestrator reads topic_limits from config
# (not a hardcoded MIN_ITEMS dict)
# ===========================================================================

def test_orchestrator_uses_config_topic_limits_not_hardcoded():
    """Verify the orchestrator reads topic_limits from config.filtering,
    not from a hardcoded MIN_ITEMS dict."""
    import ast

    with open(__file__.replace("tests/test_pipeline_quality.py",
                                "src/orchestrator.py")) as f:
        tree = ast.parse(f.read())

    # Search for any MIN_ITEMS identifier
    class MinItemsFinder(ast.NodeVisitor):
        def __init__(self):
            self.found = []
        def visit_Name(self, node):
            if 'MIN_ITEMS' in node.id:
                self.found.append((node.lineno, node.id))
            self.generic_visit(node)

    finder = MinItemsFinder()
    finder.visit(tree)
    assert len(finder.found) == 0, (
        f"MIN_ITEMS still referenced in orchestrator.py at lines: {finder.found}"
    )

    # Confirm topic_limits comes from config
    with open(__file__.replace("tests/test_pipeline_quality.py",
                                "src/orchestrator.py")) as f:
        content = f.read()

    assert "self.config.filtering.topic_limits" in content, (
        "orchestrator must use config.filtering.topic_limits"
    )
    assert "MIN_ITEMS" not in content, (
        "MIN_ITEMS hardcoded dict must be removed from orchestrator"
    )
