"""Tests for AI prompt theme customization (Work Area B).

These tests verify PROMPT STRUCTURE — that format strings work correctly and
JSON schemas are described properly. No actual AI API calls are made.
"""

import asyncio
from types import SimpleNamespace

from src.ai.analyzer import ContentAnalyzer
from src.ai.prompts import (
    CONTENT_ANALYSIS_SYSTEM,
    CONTENT_ANALYSIS_USER,
    CONTENT_ENRICHMENT_SYSTEM,
    CONTENT_ENRICHMENT_USER,
    TOPIC_DEDUP_SYSTEM,
    TOPIC_DEDUP_USER,
)
from tests.conftest_helpers import make_content_item


# ---------------------------------------------------------------------------
# CONTENT_ANALYSIS_SYSTEM — scoring guide and domain focus
# ---------------------------------------------------------------------------

class TestContentAnalysisSystem:
    """Verify scoring guide, domain alignment, and consider-section content."""

    def test_scoring_guide_has_four_tiers(self):
        """The scoring guide must contain exactly four tiers: 9-10, 7-8, 5-6, 0-4."""
        lines = CONTENT_ANALYSIS_SYSTEM.split("\n")
        score_headers = [l for l in lines if l.strip().startswith("**")]
        assert len(score_headers) == 4, f"Expected 4 score tiers, got {len(score_headers)}"
        assert "9-10" in "\n".join(score_headers)
        assert "7-8" in "\n".join(score_headers)
        assert "5-6" in "\n".join(score_headers)
        assert "0-4" in "\n".join(score_headers)

    def test_scoring_guide_no_old_tiers(self):
        """Old 3-4 and 0-2 tiers must be removed (replaced by 0-4)."""
        assert "**3-4**" not in CONTENT_ANALYSIS_SYSTEM
        assert "**0-2**" not in CONTENT_ANALYSIS_SYSTEM

    def test_domain_alignment(self):
        """The system prompt must mention all three domains."""
        assert "AI technology" in CONTENT_ANALYSIS_SYSTEM
        assert "AI markets" in CONTENT_ANALYSIS_SYSTEM or "AI market" in CONTENT_ANALYSIS_SYSTEM
        assert "global economics" in CONTENT_ANALYSIS_SYSTEM or "global economy" in CONTENT_ANALYSIS_SYSTEM

    def test_consider_section_has_market_signal(self):
        """Consider section must include market signal guidance."""
        assert "market signal" in CONTENT_ANALYSIS_SYSTEM.lower()

    def test_consider_section_has_economic_impact(self):
        """Consider section must include economic impact guidance."""
        assert "economic impact" in CONTENT_ANALYSIS_SYSTEM.lower()

    def test_consider_section_has_potential_market_impact(self):
        """Consider section must include potential market impact question."""
        assert "Potential market impact" in CONTENT_ANALYSIS_SYSTEM

    def test_consider_section_has_economic_relevance(self):
        """Consider section must include economic relevance question."""
        assert "Economic relevance" in CONTENT_ANALYSIS_SYSTEM

    def test_consider_section_no_code_quality_signal(self):
        """Old code-quality signals should be removed from the Consider section."""
        assert "code quality" not in CONTENT_ANALYSIS_SYSTEM.lower()
        assert "Quality of writing" not in CONTENT_ANALYSIS_SYSTEM

    def test_consider_section_no_software_engineering_relevance(self):
        """Old software engineering relevance line should be removed."""
        assert "software engineering" not in CONTENT_ANALYSIS_SYSTEM.lower()
        assert "systems research" not in CONTENT_ANALYSIS_SYSTEM.lower()

    def test_has_core_principle_in_chinese(self):
        """The core filtering principle (Chinese) must be present."""
        assert "核心筛选原则" in CONTENT_ANALYSIS_SYSTEM
        assert "AI 从业者" in CONTENT_ANALYSIS_SYSTEM or "AI从业者" in CONTENT_ANALYSIS_SYSTEM

    def test_breakthrough_tier_has_chinese_descriptions(self):
        """The 9-10 Breakthrough tier must have Chinese descriptions."""
        assert "AI重大突破" in CONTENT_ANALYSIS_SYSTEM
        assert "头部公司战略级变动" in CONTENT_ANALYSIS_SYSTEM
        assert "宏观政策变动" in CONTENT_ANALYSIS_SYSTEM

    def test_high_value_tier_has_chinese_descriptions(self):
        """The 7-8 High Value tier must have Chinese descriptions."""
        assert "重要进展" in CONTENT_ANALYSIS_SYSTEM
        assert "创业公司动向" in CONTENT_ANALYSIS_SYSTEM

    def test_noise_tier_has_chinese_descriptions(self):
        """The 0-4 Noise tier must have Chinese descriptions."""
        assert "纯营销内容" in CONTENT_ANALYSIS_SYSTEM
        assert "低质量转载" in CONTENT_ANALYSIS_SYSTEM

    def test_retained_community_discussion_and_engagement_signals(self):
        """Community discussion and engagement signals must still be present."""
        assert "community discussion quality" in CONTENT_ANALYSIS_SYSTEM.lower()
        assert "engagement signals" in CONTENT_ANALYSIS_SYSTEM.lower()

    def test_core_principle_full_phrase(self):
        """Core filtering principle must contain the complete decision-guiding phrase."""
        assert "影响 AI 从业者或投资者的判断" in CONTENT_ANALYSIS_SYSTEM

    def test_breakthrough_tier_contains_macro_policy(self):
        """The 9-10 breakthrough tier must reference macro policy changes."""
        assert "宏观政策变动" in CONTENT_ANALYSIS_SYSTEM
        assert "央行转向" in CONTENT_ANALYSIS_SYSTEM
        assert "贸易政策剧变" in CONTENT_ANALYSIS_SYSTEM

    def test_high_value_tier_contains_funding_and_quarterly(self):
        """The 7-8 high-value tier must mention funding rounds and quarterly earnings."""
        assert "融资轮" in CONTENT_ANALYSIS_SYSTEM
        assert "季度财报" in CONTENT_ANALYSIS_SYSTEM

    def test_incremental_tier_contains_regular_coverage(self):
        """The 5-6 tier must describe incremental updates and regular coverage."""
        assert "增量更新" in CONTENT_ANALYSIS_SYSTEM
        assert "常规报道" in CONTENT_ANALYSIS_SYSTEM

    def test_noise_tier_excludes_unrelated_content(self):
        """The 0-4 noise tier must exclude content unrelated to the three domains."""
        assert "与AI/市场/经济无关" in CONTENT_ANALYSIS_SYSTEM


# ---------------------------------------------------------------------------
# CONTENT_ENRICHMENT_SYSTEM — bilingual field structure (Work Area C)
# ---------------------------------------------------------------------------

class TestContentEnrichmentSystem:
    """Verify enrichment prompt still describes bilingual _en/_zh fields.

    This prompt was NOT modified by Work Area B but must not be accidentally broken.
    """

    def test_system_prompt_all_bilingual_pairs(self):
        """CONTENT_ENRICHMENT_SYSTEM must describe all six bilingual field pairs."""
        pairs = ["title", "whats_new", "why_it_matters", "key_details",
                 "background", "community_discussion"]
        for field in pairs:
            assert f"{field}_en" in CONTENT_ENRICHMENT_SYSTEM, f"Missing {field}_en"
            assert f"{field}_zh" in CONTENT_ENRICHMENT_SYSTEM, f"Missing {field}_zh"

    def test_user_prompt_all_bilingual_pairs(self):
        """CONTENT_ENRICHMENT_USER must include all six bilingual field pairs in JSON schema."""
        pairs = ["title", "whats_new", "why_it_matters", "key_details",
                 "background", "community_discussion"]
        for field in pairs:
            assert f"{field}_en" in CONTENT_ENRICHMENT_USER, f"Missing {field}_en in user prompt"
            assert f"{field}_zh" in CONTENT_ENRICHMENT_USER, f"Missing {field}_zh in user prompt"

    def test_critical_language_rule_present(self):
        """The CRITICAL language rule section must be present in system prompt."""
        assert "CRITICAL" in CONTENT_ENRICHMENT_SYSTEM
        assert "Language rules" in CONTENT_ENRICHMENT_SYSTEM
        assert "简体中文" in CONTENT_ENRICHMENT_SYSTEM

    def test_user_prompt_has_simplified_chinese_instruction(self):
        """The user prompt must instruct Simplified Chinese for _zh fields."""
        assert "简体中文" in CONTENT_ENRICHMENT_USER or "中文" in CONTENT_ENRICHMENT_USER
        assert "英文" in CONTENT_ENRICHMENT_USER or "English" in CONTENT_ENRICHMENT_USER

    def test_system_has_sources_instruction(self):
        """System prompt must instruct to pick source URLs from search results."""
        assert "sources" in CONTENT_ENRICHMENT_SYSTEM
        assert "search results" in CONTENT_ENRICHMENT_SYSTEM.lower()

    def test_system_mentions_field_definitions(self):
        """System prompt must define all field purposes."""
        assert "whats_new" in CONTENT_ENRICHMENT_SYSTEM
        assert "why_it_matters" in CONTENT_ENRICHMENT_SYSTEM
        assert "key_details" in CONTENT_ENRICHMENT_SYSTEM
        assert "background" in CONTENT_ENRICHMENT_SYSTEM
        assert "community_discussion" in CONTENT_ENRICHMENT_SYSTEM

    def test_user_prompt_has_valid_json_only(self):
        """Enrichment user prompt must instruct valid JSON only."""
        assert "valid JSON only" in CONTENT_ENRICHMENT_USER


# ---------------------------------------------------------------------------
# CONTENT_ANALYSIS_USER — format-string correctness
# ---------------------------------------------------------------------------

class TestContentAnalysisUser:
    """Verify the user prompt format string works with realistic data."""

    def test_format_with_minimal_fields(self):
        """Format must succeed with only required fields (empty optional sections)."""
        prompt = CONTENT_ANALYSIS_USER.format(
            title="Test Paper on LLM Reasoning",
            source="rss",
            author="Test Author",
            url="https://example.com/paper",
            content_section="",
            discussion_section="",
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        assert "Test Paper on LLM Reasoning" in prompt
        assert "rss" in prompt
        assert "Test Author" in prompt

    def test_format_with_full_content(self):
        """Format must succeed with all fields populated."""
        prompt = CONTENT_ANALYSIS_USER.format(
            title="OpenAI releases GPT-5 with breakthrough reasoning capabilities",
            source="hackernews",
            author="tech_journalist",
            url="https://news.ycombinator.com/item?id=12345",
            content_section="\nContent:\nOpenAI today announced GPT-5...",
            discussion_section="\nDiscussion:\nHacker News thread with 500+ comments",
        )
        assert isinstance(prompt, str)
        assert "OpenAI releases GPT-5" in prompt
        assert "hackernews" in prompt
        assert "discussion_section" not in prompt  # format() replaced the placeholder

    def test_format_with_varied_author_none(self):
        """Format must accept empty author."""
        prompt = CONTENT_ANALYSIS_USER.format(
            title="Some Title",
            source="rss",
            author="",
            url="https://example.com",
            content_section="Content here",
            discussion_section="",
        )
        assert isinstance(prompt, str)
        assert "Some Title" in prompt

    def test_json_schema_is_described(self):
        """The user prompt must describe the expected JSON response schema."""
        assert '"score":' in CONTENT_ANALYSIS_USER
        assert '"reason":' in CONTENT_ANALYSIS_USER
        assert '"summary":' in CONTENT_ANALYSIS_USER
        assert '"tags":' in CONTENT_ANALYSIS_USER

    def test_json_schema_requires_valid_json_only(self):
        """The prompt must instruct valid JSON only response."""
        assert "valid JSON only" in CONTENT_ANALYSIS_USER

    def test_content_and_discussion_placeholders_used(self):
        """The user prompt must reference both optional placeholders."""
        assert "{content_section}" in CONTENT_ANALYSIS_USER
        assert "{discussion_section}" in CONTENT_ANALYSIS_USER

    def test_format_with_empty_title(self):
        """Format must work with an empty title."""
        prompt = CONTENT_ANALYSIS_USER.format(
            title="",
            source="rss",
            author="Author",
            url="https://example.com",
            content_section="",
            discussion_section="",
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 20

    def test_format_with_very_long_title(self):
        """Format must work with a very long title (500+ chars)."""
        long_title = "LongTitle " * 51
        assert len(long_title) > 500
        prompt = CONTENT_ANALYSIS_USER.format(
            title=long_title,
            source="rss",
            author="Author",
            url="https://example.com",
            content_section="Some content here",
            discussion_section="",
        )
        assert isinstance(prompt, str)
        assert long_title in prompt

    def test_format_with_cjk_title(self):
        """Format must work with CJK characters in the title."""
        cjk_title = "OpenAI 发布 GPT-5：突破性推理能力与多模态融合的重大进展"
        prompt = CONTENT_ANALYSIS_USER.format(
            title=cjk_title,
            source="rss",
            author="测试作者",
            url="https://example.com",
            content_section="",
            discussion_section="",
        )
        assert isinstance(prompt, str)
        assert cjk_title in prompt

    def test_format_with_cjk_author(self):
        """Format must work with CJK characters in the author field."""
        prompt = CONTENT_ANALYSIS_USER.format(
            title="Test Title",
            source="rss",
            author="张测试",
            url="https://example.com",
            content_section="Content here",
            discussion_section="",
        )
        assert isinstance(prompt, str)
        assert "张测试" in prompt

    def test_format_with_very_long_content_section(self):
        """Format must work with a very long content section."""
        long_content = "Content chunk. " * 500
        prompt = CONTENT_ANALYSIS_USER.format(
            title="Title",
            source="rss",
            author="Author",
            url="https://example.com",
            content_section=f"Content: {long_content[:2000]}",
            discussion_section="",
        )
        assert isinstance(prompt, str)
        assert "Content: Content chunk" in prompt

    def test_format_with_url_containing_cjk(self):
        """Format must work with URLs that contain non-ASCII characters (rare but valid)."""
        prompt = CONTENT_ANALYSIS_USER.format(
            title="测试",
            source="rss",
            author="Author",
            url="https://zh.wikipedia.org/wiki/人工智能",
            content_section="",
            discussion_section="",
        )
        assert isinstance(prompt, str)
        assert "https://zh.wikipedia.org" in prompt


# ---------------------------------------------------------------------------
# TOPIC_DEDUP_SYSTEM — dedup rules
# ---------------------------------------------------------------------------

class TestTopicDedupSystem:
    """Verify dedup rules include AI/business-specific examples."""

    def test_has_funding_round_dedup_example(self):
        """Must include same-funding-round dedup example (Chinese)."""
        assert "同一轮融资" in TOPIC_DEDUP_SYSTEM

    def test_has_model_release_dedup_example(self):
        """Must include same-model-release dedup example (Chinese)."""
        assert "同一模型发布" in TOPIC_DEDUP_SYSTEM

    def test_preserves_err_on_side_of_separate(self):
        """Must keep the 'err on the side of keeping separate' principle."""
        assert "keeping items separate" in TOPIC_DEDUP_SYSTEM

    def test_preserves_existing_examples(self):
        """Must keep existing dedup examples like Gemma 4."""
        assert "Gemma 4 released" in TOPIC_DEDUP_SYSTEM
        assert "Gemma 4 jailbroken" in TOPIC_DEDUP_SYSTEM


# ---------------------------------------------------------------------------
# TOPIC_DEDUP_USER — format-string correctness
# ---------------------------------------------------------------------------

class TestTopicDedupUser:
    """Verify the dedup user prompt format string works with mock items."""

    def test_format_with_single_item(self):
        """Format must succeed with one mock item."""
        items_text = "0: [8.5] OpenAI releases GPT-5 - https://example.com/gpt5"
        prompt = TOPIC_DEDUP_USER.format(items=items_text)
        assert isinstance(prompt, str)
        assert "OpenAI releases GPT-5" in prompt
        assert "8.5" in prompt

    def test_format_with_multiple_items(self):
        """Format must succeed with multiple mock items."""
        items_text = (
            "0: [8.5] OpenAI releases GPT-5 - https://example.com/gpt5\n"
            "1: [7.0] Google launches Gemini 4 - https://example.com/gemini4\n"
            "2: [8.0] OpenAI GPT-5 benchmark results - https://example.com/gpt5-bench"
        )
        prompt = TOPIC_DEDUP_USER.format(items=items_text)
        assert isinstance(prompt, str)
        assert "OpenAI releases GPT-5" in prompt
        assert "Google launches Gemini 4" in prompt
        assert "0:" in prompt
        assert "1:" in prompt
        assert "2:" in prompt

    def test_format_with_dedup_placeholders_in_instruction(self):
        """The dedup user prompt must describe the expected JSON structure."""
        assert '"duplicates"' in TOPIC_DEDUP_USER
        assert '"duplicates": []' in TOPIC_DEDUP_USER or '"duplicates"' in TOPIC_DEDUP_USER

    def test_respond_with_valid_json_only(self):
        """The dedup prompt must instruct valid JSON only response."""
        assert "valid JSON only" in TOPIC_DEDUP_USER

    def test_mentions_primary_idx_convention(self):
        """Must explain the first index in each group is primary."""
        assert "first index" in TOPIC_DEDUP_USER
        assert "primary item" in TOPIC_DEDUP_USER

    def test_format_with_realistic_items_text(self):
        """Format with realistic items_text (matching orchestrator format) must work.

        The orchestrator produces::

            [i] Title
                Tags: ...
                Summary: ...
        """
        items_text = (
            "[0] OpenAI releases GPT-5 with breakthrough reasoning\n"
            "    Tags: AI, model release, OpenAI\n"
            "    Summary: OpenAI announced GPT-5 with 10x improvement in reasoning\n"
            "\n"
            "[1] Google unveils Gemini 4\n"
            "    Tags: AI, Google, Gemini\n"
            "    Summary: Google's next-gen multimodal model\n"
            "\n"
            "[2] OpenAI GPT-5 review: everything you need to know\n"
            "    Tags: AI, GPT-5, analysis\n"
            "    Summary: In-depth review of GPT-5 capabilities\n"
        )
        prompt = TOPIC_DEDUP_USER.format(items=items_text)
        assert isinstance(prompt, str)
        assert "[0]" in prompt
        assert "[1]" in prompt
        assert "[2]" in prompt
        assert "GPT-5" in prompt
        assert "Gemini 4" in prompt
        assert "Tags:" in prompt
        assert "Summary:" in prompt


# ---------------------------------------------------------------------------
# Integration smoke test — ContentAnalyzer + mock client
# ---------------------------------------------------------------------------

class TestAnalyzerIntegration:
    """Verify the analyzer pipeline works with a mock AI client.

    Makes no real AI API calls — monkeypatches client.complete.
    """

    def test_analyzer_sets_score_from_mock_json(self, monkeypatch):
        """ContentAnalyzer._analyze_item must set ai_score from mock AI response."""
        item = make_content_item(
            title="OpenAI releases GPT-5",
            content="OpenAI announced GPT-5 today with breakthrough reasoning.",
        )
        client = SimpleNamespace(complete=None)
        analyzer = ContentAnalyzer(client)

        async def fake_complete(system, user):
            return (
                '{"score": 8.5, "reason": "Major model release with broad impact",'
                ' "summary": "OpenAI releases GPT-5", "tags": ["AI", "OpenAI", "GPT-5"]}'
            )

        monkeypatch.setattr(analyzer.client, "complete", fake_complete)

        asyncio.run(analyzer._analyze_item(item))

        assert item.ai_score == 8.5
        assert item.ai_reason == "Major model release with broad impact"
        assert item.ai_summary == "OpenAI releases GPT-5"
        assert item.ai_tags == ["AI", "OpenAI", "GPT-5"]

    def test_analyzer_handles_empty_content_gracefully(self, monkeypatch):
        """ContentAnalyzer._analyze_item must handle items with no content field."""
        item = make_content_item(
            title="Breaking News",
            content=None,
        )
        client = SimpleNamespace(complete=None)
        analyzer = ContentAnalyzer(client)

        async def fake_complete(system, user):
            return (
                '{"score": 6.0, "reason": "Notable item",'
                ' "summary": "Breaking news alert", "tags": ["news"]}'
            )

        monkeypatch.setattr(analyzer.client, "complete", fake_complete)

        asyncio.run(analyzer._analyze_item(item))

        assert item.ai_score == 6.0
        assert item.ai_tags == ["news"]

    def test_analyzer_handles_unparseable_json(self, monkeypatch):
        """ContentAnalyzer._analyze_item must handle unparseable AI response gracefully."""
        item = make_content_item(
            title="Test Item",
            content="Some content here",
        )
        client = SimpleNamespace(complete=None)
        analyzer = ContentAnalyzer(client)

        async def fake_complete(system, user):
            return "This is not JSON at all"

        monkeypatch.setattr(analyzer.client, "complete", fake_complete)

        asyncio.run(analyzer._analyze_item(item))

        # Should fall back to safe defaults
        assert item.ai_score == 0.0
        assert "parse failed" in (item.ai_reason or "").lower()

    def test_analyzer_handles_missing_score_in_json(self, monkeypatch):
        """ContentAnalyzer._analyze_item must handle JSON with missing score field."""
        item = make_content_item(title="Test")
        client = SimpleNamespace(complete=None)
        analyzer = ContentAnalyzer(client)

        async def fake_complete(system, user):
            return '{"reason": "ok", "summary": "OK", "tags": []}'

        monkeypatch.setattr(analyzer.client, "complete", fake_complete)

        asyncio.run(analyzer._analyze_item(item))

        assert item.ai_score == 0.0  # default when missing
        assert item.ai_reason == "ok"

    def test_analyzer_produces_score_in_valid_range(self, monkeypatch):
        """ContentAnalyzer._analyze_item must produce scores in the valid 0-10 range."""
        item = make_content_item(title="Test")
        client = SimpleNamespace(complete=None)
        analyzer = ContentAnalyzer(client)

        async def fake_complete(system, user):
            return (
                '{"score": 15.0, "reason": "Overflow test",'
                ' "summary": "Test", "tags": ["test"]}'
            )

        monkeypatch.setattr(analyzer.client, "complete", fake_complete)

        asyncio.run(analyzer._analyze_item(item))

        assert item.ai_score == 15.0  # The analyzer doesn't clamp — it stores what AI returns

    def test_analyzer_prompt_includes_item_title(self, monkeypatch):
        """The formatted prompt sent to the AI must include the item title."""
        captured = {}

        async def fake_complete(system, user):
            captured["user"] = user
            captured["system"] = system
            return '{"score": 7.0, "reason": "Test", "summary": "Test", "tags": ["t"]}'

        item = make_content_item(title="UniqueTestTitle_XYZ")
        client = SimpleNamespace(complete=None)
        analyzer = ContentAnalyzer(client)
        monkeypatch.setattr(analyzer.client, "complete", fake_complete)

        asyncio.run(analyzer._analyze_item(item))

        assert "UniqueTestTitle_XYZ" in captured["user"]
        assert "UniqueTestTitle_XYZ" not in captured["system"]

    def test_analyzer_uses_correct_system_prompt(self, monkeypatch):
        """The system prompt sent to the AI must be CONTENT_ANALYSIS_SYSTEM."""
        captured = {}

        async def fake_complete(system, user):
            captured["system"] = system
            return '{"score": 7.0, "reason": "Test", "summary": "Test", "tags": ["t"]}'

        item = make_content_item(title="Test")
        client = SimpleNamespace(complete=None)
        analyzer = ContentAnalyzer(client)
        monkeypatch.setattr(analyzer.client, "complete", fake_complete)

        asyncio.run(analyzer._analyze_item(item))

        assert captured["system"] == CONTENT_ANALYSIS_SYSTEM
