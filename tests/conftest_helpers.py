"""Helper factories for creating mock test data.

Provides factory functions that produce valid Horizon model instances
for use across all test files.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.models import (
    AIConfig,
    AIProvider,
    Config,
    ContentItem,
    FilteringConfig,
    HackerNewsConfig,
    OSSInsightConfig,
    RedditConfig,
    RSSSourceConfig,
    SourceType,
    SourcesConfig,
)


def make_content_item(
    item_id: str = "rss:test:1",
    source_type: SourceType = SourceType.RSS,
    title: str = "Test Item",
    url: str = "https://example.com/test-item",
    content: Optional[str] = "This is test content.",
    author: Optional[str] = "Test Author",
    published_at: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ai_score: Optional[float] = None,
    ai_reason: Optional[str] = None,
    ai_summary: Optional[str] = None,
    ai_tags: Optional[List[str]] = None,
) -> ContentItem:
    """Create a ContentItem with sensible defaults for testing.

    All fields except the primary identifiers have defaults so tests can
    concisely create only the fields they need.

    Args:
        item_id: Unique item identifier, default ``"rss:test:1"``.
        source_type: Source type enum, default ``SourceType.RSS``.
        title: Item title.
        url: Item URL (any string — Pydantic's ``HttpUrl`` validates it).
        content: Item body text, default ``"This is test content."``.
                  Pass ``None`` for no content.
        author: Author name.
        published_at: Publication timestamp. Defaults to ``2026-05-31T00:00Z``.
        metadata: Arbitrary key-value dict.
        ai_score: AI importance score (0-10).
        ai_reason: AI reasoning text.
        ai_summary: AI one-sentence summary.
        ai_tags: AI-assigned tags.

    Returns:
        A fully valid ``ContentItem``.
    """
    return ContentItem(
        id=item_id,
        source_type=source_type,
        title=title,
        url=url,
        content=content,
        author=author,
        published_at=published_at or datetime(2026, 5, 31, tzinfo=timezone.utc),
        metadata=metadata or {},
        ai_score=ai_score,
        ai_reason=ai_reason,
        ai_summary=ai_summary,
        ai_tags=ai_tags or [],
    )


def make_config(
    provider: AIProvider = AIProvider.DEEPSEEK,
    model: str = "deepseek-chat",
    api_key_env: str = "DEEPSEEK_API_KEY",
    languages: Optional[List[str]] = None,
    rss_sources: Optional[List[RSSSourceConfig]] = None,
    threshold: float = 6.0,
    time_window_hours: int = 24,
) -> Config:
    """Create a minimal valid Config for testing.

    The returned Config has:
    - A configurable AI provider (default DeepSeek).
    - A single mock RSS feed if no ``rss_sources`` are given.
    - HackerNews and Reddit enabled with default values.
    - All other optional sources disabled.
    - A filtering config with the given threshold.

    Args:
        provider: AI provider enum.
        model: Model name string.
        api_key_env: Environment variable name for the API key.
        languages: List of language codes (default ``["en"]``).
        rss_sources: RSS feed configurations. If ``None``, a single
                      mock feed is created.
        threshold: ``ai_score_threshold`` value.
        time_window_hours: ``time_window_hours`` value.

    Returns:
        A fully valid ``Config``.
    """
    if rss_sources is None:
        rss_sources = [
            RSSSourceConfig(
                name="Test Feed",
                url="https://example.com/feed.xml",
                enabled=True,
            )
        ]

    return Config(
        ai=AIConfig(
            provider=provider,
            model=model,
            api_key_env=api_key_env,
            languages=languages or ["en"],
        ),
        sources=SourcesConfig(
            rss=rss_sources,
            hackernews=HackerNewsConfig(enabled=True),
            reddit=RedditConfig(enabled=True),
            ossinsight=OSSInsightConfig(enabled=False),
        ),
        filtering=FilteringConfig(
            ai_score_threshold=threshold,
            time_window_hours=time_window_hours,
        ),
    )
