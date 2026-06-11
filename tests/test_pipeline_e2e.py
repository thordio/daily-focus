"""End-to-end pipeline smoke test for Areas C + F.

Exercises the complete flow with mock data:
  ContentItems -> ImageSelector.select_images() ->
  DailySummarizer.get_structured_data() -> DailyRenderer.render_html()

Uses monkeypatched AI clients so it does NOT need DEEPSEEK_API_KEY.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from src.ai.image_selector import ImageSelector
from src.ai.summarizer import DailySummarizer
from src.renderer import DailyRenderer
from src.models import ContentItem, SourceType
from tests.conftest_helpers import make_content_item


def _make_enriched_item(
    item_id: str,
    title: str,
    title_en: str,
    url: str,
    score: float,
    score_reason: str,
    feed_name: str,
    detailed_summary_zh: str,
    detailed_summary_en: str,
    background_zh: str,
    background_en: str,
    community_discussion_zh: str = "",
    community_discussion_en: str = "",
    tags: list | None = None,
    candidate_images: list | None = None,
) -> ContentItem:
    """Build a ContentItem as it would appear after enrichment with optional candidate_images."""
    md = {
        "title_en": title_en,
        "feed_name": feed_name,
        "detailed_summary_zh": detailed_summary_zh,
        "detailed_summary_en": detailed_summary_en,
        "background_zh": background_zh,
        "background_en": background_en,
    }
    if community_discussion_zh:
        md["community_discussion_zh"] = community_discussion_zh
    if community_discussion_en:
        md["community_discussion_en"] = community_discussion_en
    if candidate_images:
        md["candidate_images"] = candidate_images

    return make_content_item(
        item_id=item_id,
        source_type=SourceType.RSS,
        title=title,
        url=url,
        ai_score=score,
        ai_reason=score_reason,
        ai_summary=detailed_summary_zh,
        ai_tags=tags or [],
        metadata=md,
        published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


def test_pipeline_e2e_full_flow():
    """Full pipeline: mock items -> select_images -> structured_data -> render_html."""
    # --- Arrange: create enriched items with candidate images ---
    items = [
        _make_enriched_item(
            item_id="e2e:1",
            title="OpenAI 发布 GPT-5",
            title_en="OpenAI Releases GPT-5",
            url="https://example.com/gpt5",
            score=9.2,
            score_reason="Major model release",
            feed_name="TechCrunch",
            detailed_summary_zh="OpenAI 正式发布了 GPT-5。",
            detailed_summary_en="OpenAI officially released GPT-5.",
            background_zh="GPT-5 是最新一代大语言模型。",
            background_en="GPT-5 is the latest LLM.",
            community_discussion_zh="社区反应热烈。",
            community_discussion_en="The community is excited.",
            tags=["AI", "OpenAI"],
            candidate_images=[
                {"url": "https://example.com/benchmark.png", "alt": "GPT-5 vs Claude 4 benchmark MMLU", "before": "benchmark comparison", "after": "significant improvement"},
                {"url": "https://example.com/team-photo.jpg", "alt": "OpenAI team", "before": "team photo at", "after": "launch event"},
            ],
        ),
        _make_enriched_item(
            item_id="e2e:2",
            title="DeepSeek 发布 V4",
            title_en="DeepSeek Releases V4",
            url="https://example.com/deepseek-v4",
            score=7.5,
            score_reason="Important open-source release",
            feed_name="机器之心",
            detailed_summary_zh="DeepSeek 发布了 V4 模型。",
            detailed_summary_en="DeepSeek released V4 model.",
            background_zh="DeepSeek V4 是开源大模型。",
            background_en="DeepSeek V4 is an open-source LLM.",
            tags=["AI", "DeepSeek"],
            candidate_images=[
                {"url": "https://example.com/chart.png", "alt": "Performance benchmarks comparison", "before": "chart shows", "after": "performance metrics"},
            ],
        ),
        _make_enriched_item(
            item_id="e2e:3",
            title="Market news text only",
            title_en="Market News Text Only",
            url="https://example.com/market",
            score=6.0,
            score_reason="Routine market update",
            feed_name="Reuters",
            detailed_summary_zh="市场消息。",
            detailed_summary_en="Market update.",
            background_zh="常规市场动态。",
            background_en="Regular market activity.",
            tags=["economy"],
            # No candidate_images — item without images
        ),
    ]

    # --- Act Step 1: ImageSelector with mocked AI ---
    mock_client = AsyncMock()
    mock_client.complete.return_value = json.dumps({
        "results": [
            {"index": 0, "category": "informational", "confidence": 0.95},
            {"index": 1, "category": "decorative", "confidence": 0.88},
            {"index": 2, "category": "informational", "confidence": 0.92},
        ]
    })
    selector = ImageSelector(mock_client)
    asyncio.run(selector.select_images(items))

    # --- Verify Step 1: Image selection ---
    # Item 0: first image is informational, second is decorative -> only first selected
    selected_0 = items[0].metadata.get("selected_images", [])
    assert len(selected_0) == 1
    assert selected_0[0]["url"] == "https://example.com/benchmark.png"
    assert selected_0[0]["alt"] == "GPT-5 vs Claude 4 benchmark MMLU"

    # Item 1: its single image is informational -> selected
    selected_1 = items[1].metadata.get("selected_images", [])
    assert len(selected_1) == 1
    assert "chart.png" in selected_1[0]["url"]

    # Item 2: no candidates -> no selected_images
    assert "selected_images" not in items[2].metadata

    # --- Act Step 2: get_structured_data ---
    today = "2026-06-01"
    summarizer = DailySummarizer()

    for lang in ("zh", "en"):
        for period in ("morning", "evening"):
            data = summarizer.get_structured_data(
                items, today, total_fetched=50,
                language=lang, period=period,
            )

            # --- Verify Step 2: structured data ---
            assert data["date"] == today
            assert data["period"] == period
            assert data["language"] == lang
            assert data["total_fetched"] == 50
            assert data["selected_count"] == 3
            assert len(data["items"]) == 3

            # Item 0 should have its selected image
            assert len(data["items"][0]["images"]) == 1
            assert data["items"][0]["images"][0]["alt"] == "GPT-5 vs Claude 4 benchmark MMLU"

            # Item 2 should have no images
            assert data["items"][2]["images"] == []

            # --- Act Step 3: render_html ---
            renderer = DailyRenderer()
            html = renderer.render_html(data)

            # --- Verify Step 3: HTML output ---
            assert "<!DOCTYPE html>" in html
            assert "GPT-5" in html
            assert "DeepSeek" in html
            assert "Market" in html or "market" in html.lower()

            # Title is always "Daily Focus"
            expected_title = "Daily Focus"
            assert expected_title in html


def test_pipeline_e2e_empty_items():
    """Pipeline handles empty items list gracefully end-to-end."""
    summarizer = DailySummarizer()
    renderer = DailyRenderer()

    data = summarizer.get_structured_data([], "2026-06-01", 10, "zh", "morning")
    assert data["selected_count"] == 0
    assert data["items"] == []

    html = renderer.render_html(data)
    assert "<!DOCTYPE html>" in html
    assert "noindex" in html
    # Should show empty state message
    assert "暂无重要动态" in html or "No significant developments" in html


def test_pipeline_e2e_image_selector_skipped():
    """Pipeline works when ImageSelector is not called (no candidate_images set)."""
    items = [
        _make_enriched_item(
            item_id="e2e:noimg:1",
            title="Just text",
            title_en="Just Text",
            url="https://example.com/text",
            score=8.0,
            score_reason="Test item",
            feed_name="Test",
            detailed_summary_zh="纯文本条目。",
            detailed_summary_en="Plain text item.",
            background_zh="无图片。",
            background_en="No images.",
            tags=["test"],
            candidate_images=None,  # No candidates
        ),
    ]

    summarizer = DailySummarizer()
    data = summarizer.get_structured_data(items, "2026-06-01", 10, "zh", "morning")

    assert data["items"][0]["images"] == []

    renderer = DailyRenderer()
    html = renderer.render_html(data)
    assert "Just text" in html or "text" in html.lower()
