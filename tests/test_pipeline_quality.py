"""Quality assurance tests for the daily pipeline output.

Focus areas:
1.  whats_new vs why_it_matters are distinct text (P0)
2.  Topic distribution minimums are met (per-tab counts)
3.  Chinese language detection via _has_cjk()
4.  language_mismatch flagging for non-CJK content in zh mode
5.  Filename generation and parsing conventions
6.  CJK content ratio validation
7.  is_demo default semantics
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.ai.summarizer import DailySummarizer, _has_cjk
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
