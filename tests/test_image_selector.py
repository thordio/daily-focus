"""Tests for ImageSelector (Work Area F)."""

from __future__ import annotations

import asyncio
import json as json_mod
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from src.ai.image_selector import ImageSelector
from src.ai.prompts import IMAGE_SELECTION_SYSTEM, IMAGE_SELECTION_USER
from src.models import ContentItem, SourceType


class TestPrompts:
    """Verify IMAGE_SELECTION prompt structure."""

    def test_system_prompt_has_categories(self):
        """System prompt must define both categories."""
        assert "informational" in IMAGE_SELECTION_SYSTEM
        assert "decorative" in IMAGE_SELECTION_SYSTEM

    def test_user_prompt_has_placeholders(self):
        """User prompt must contain format placeholders."""
        assert "{n}" in IMAGE_SELECTION_USER
        assert "{images_json}" in IMAGE_SELECTION_USER

    def test_user_prompt_has_json_schema(self):
        """User prompt must describe expected JSON response."""
        assert '"results"' in IMAGE_SELECTION_USER
        assert '"index"' in IMAGE_SELECTION_USER
        assert '"category"' in IMAGE_SELECTION_USER
        assert '"confidence"' in IMAGE_SELECTION_USER


class TestImageSelector:
    """Tests for ImageSelector class."""

    def test_import(self):
        """ImageSelector can be imported and instantiated."""
        mock_client = AsyncMock()
        selector = ImageSelector(mock_client)
        assert selector is not None
        assert selector.client is mock_client

    def test_empty_candidates_no_crash(self):
        """Empty candidate lists should not cause errors."""
        mock_client = AsyncMock()
        selector = ImageSelector(mock_client)
        items = [
            ContentItem(
                id="test:1",
                source_type=SourceType.RSS,
                title="Test",
                url="https://example.com",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={},  # No candidate_images
            )
        ]

        asyncio.run(selector.select_images(items))

        # selected_images should not be set
        assert "selected_images" not in items[0].metadata
        # AI client should NOT have been called with no candidates
        mock_client.complete.assert_not_called()

    def test_invalid_json_response_degradation(self):
        """Invalid JSON from AI should silently degrade (no crash)."""
        mock_client = AsyncMock()
        # Return invalid/unparseable response
        mock_client.complete.return_value = "not valid json at all {{{ broken"
        selector = ImageSelector(mock_client)

        items = [
            ContentItem(
                id="test:1",
                source_type=SourceType.RSS,
                title="Test",
                url="https://example.com",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={
                    "candidate_images": [
                        {
                            "url": "https://example.com/img1.png",
                            "alt": "chart",
                            "before": "",
                            "after": "",
                        }
                    ]
                },
            )
        ]

        asyncio.run(selector.select_images(items))

        # Should degrade gracefully — selected_images not set
        assert "selected_images" not in items[0].metadata

    def test_api_exception_degradation(self):
        """AI client exception should silently degrade."""
        mock_client = AsyncMock()
        mock_client.complete.side_effect = RuntimeError("API connection failed")
        selector = ImageSelector(mock_client)

        items = [
            ContentItem(
                id="test:1",
                source_type=SourceType.RSS,
                title="Test",
                url="https://example.com",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={
                    "candidate_images": [
                        {
                            "url": "https://example.com/img1.png",
                            "alt": "chart",
                            "before": "",
                            "after": "",
                        }
                    ]
                },
            )
        ]

        asyncio.run(selector.select_images(items))

        # Should degrade gracefully
        assert "selected_images" not in items[0].metadata

    def test_informational_images_selected(self):
        """Images classified as informational are written to selected_images."""
        mock_client = AsyncMock()
        mock_client.complete.return_value = """
        {
            "results": [
                {"index": 0, "category": "informational", "confidence": 0.95},
                {"index": 1, "category": "decorative", "confidence": 0.88}
            ]
        }
        """
        selector = ImageSelector(mock_client)

        items = [
            ContentItem(
                id="test:1",
                source_type=SourceType.RSS,
                title="Test",
                url="https://example.com",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={
                    "candidate_images": [
                        {
                            "url": "https://example.com/chart.png",
                            "alt": "MMLU benchmark comparison",
                            "before": "chart shows",
                            "after": "significant improvement",
                        },
                        {
                            "url": "https://example.com/photo.jpg",
                            "alt": "Sam Altman",
                            "before": "CEO",
                            "after": "announced",
                        },
                    ]
                },
            )
        ]

        asyncio.run(selector.select_images(items))

        selected = items[0].metadata.get("selected_images", [])
        # Only the informational image (index 0) should be selected
        assert len(selected) == 1
        assert selected[0]["url"] == "https://example.com/chart.png"
        assert selected[0]["alt"] == "MMLU benchmark comparison"

    def test_multiple_items_separate_selections(self):
        """Images from different items are selected independently."""
        mock_client = AsyncMock()
        mock_client.complete.return_value = """
        {"results": [
            {"index": 0, "category": "informational", "confidence": 0.9},
            {"index": 1, "category": "decorative", "confidence": 0.9}
        ]}
        """
        selector = ImageSelector(mock_client)

        items = [
            ContentItem(
                id="test:1",
                source_type=SourceType.RSS,
                title="Item with chart",
                url="https://example.com/1",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={
                    "candidate_images": [
                        {
                            "url": "https://example.com/chart.png",
                            "alt": "benchmark",
                            "before": "",
                            "after": "",
                        }
                    ]
                },
            ),
            ContentItem(
                id="test:2",
                source_type=SourceType.RSS,
                title="Item with photo",
                url="https://example.com/2",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={
                    "candidate_images": [
                        {
                            "url": "https://example.com/photo.jpg",
                            "alt": "headshot",
                            "before": "",
                            "after": "",
                        }
                    ]
                },
            ),
        ]

        asyncio.run(selector.select_images(items))

        # Item 0 should have the informational image
        assert len(items[0].metadata.get("selected_images", [])) == 1
        assert items[0].metadata["selected_images"][0]["url"] == "https://example.com/chart.png"
        # Item 1 should NOT have selected_images (its image was decorative)
        assert "selected_images" not in items[1].metadata

    def test_all_decorative_images_empty_result(self):
        """All decorative images means selected_images is empty."""
        mock_client = AsyncMock()
        mock_client.complete.return_value = """
        {"results": [
            {"index": 0, "category": "decorative", "confidence": 0.95},
            {"index": 1, "category": "decorative", "confidence": 0.90}
        ]}
        """
        selector = ImageSelector(mock_client)

        items = [
            ContentItem(
                id="test:1",
                source_type=SourceType.RSS,
                title="All decorative",
                url="https://example.com/1",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={
                    "candidate_images": [
                        {"url": "https://example.com/photo1.jpg", "alt": "group photo", "before": "", "after": ""},
                        {"url": "https://example.com/logo.svg", "alt": "Company logo", "before": "", "after": ""},
                    ]
                },
            ),
        ]

        asyncio.run(selector.select_images(items))

        # No informational images — selected_images should not be set
        assert "selected_images" not in items[0].metadata

    def test_mixed_items_some_have_candidates_some_dont(self):
        """Mix of items with and without candidates — items without are untouched."""
        mock_client = AsyncMock()
        mock_client.complete.return_value = """
        {"results": [
            {"index": 0, "category": "informational", "confidence": 0.95}
        ]}
        """
        selector = ImageSelector(mock_client)

        items = [
            ContentItem(
                id="test:1",
                source_type=SourceType.RSS,
                title="Has candidates",
                url="https://example.com/1",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={
                    "candidate_images": [
                        {"url": "https://example.com/chart.png", "alt": "benchmark", "before": "", "after": ""},
                    ]
                },
            ),
            ContentItem(
                id="test:2",
                source_type=SourceType.RSS,
                title="No candidates",
                url="https://example.com/2",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={},  # No candidate_images
            ),
            ContentItem(
                id="test:3",
                source_type=SourceType.RSS,
                title="Empty candidates list",
                url="https://example.com/3",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={"candidate_images": []},
            ),
        ]

        asyncio.run(selector.select_images(items))

        # Item 0 should have the selected image
        assert len(items[0].metadata.get("selected_images", [])) == 1
        # Item 1 (no candidates) should not have selected_images
        assert "selected_images" not in items[1].metadata
        # Item 2 (empty candidates list) should not have selected_images
        assert "selected_images" not in items[2].metadata

    def test_integration_monkeypatched_client(self):
        """Integration-style test: monkeypatched AI client returns known response."""
        import json

        mock_client = AsyncMock()
        expected_response = json.dumps({
            "results": [
                {"index": 0, "category": "informational", "confidence": 0.97},
                {"index": 1, "category": "informational", "confidence": 0.85},
            ]
        })
        mock_client.complete.return_value = expected_response
        selector = ImageSelector(mock_client)

        items = [
            ContentItem(
                id="test:1",
                source_type=SourceType.RSS,
                title="Item with real chart",
                url="https://example.com/chart",
                content="",
                published_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={
                    "candidate_images": [
                        {"url": "https://example.com/chart1.png", "alt": "MMLU benchmark", "before": "chart shows", "after": "improvement"},
                        {"url": "https://example.com/chart2.png", "alt": "Performance graph", "before": "graph displays", "after": "growth"},
                    ]
                },
            ),
        ]

        asyncio.run(selector.select_images(items))

        # Both images are informational, so both should be selected
        selected = items[0].metadata.get("selected_images", [])
        assert len(selected) == 2
        assert selected[0]["url"] == "https://example.com/chart1.png"
        assert selected[1]["url"] == "https://example.com/chart2.png"

        # Verify the AI client was called with correct prompts
        assert mock_client.complete.called
        call_kwargs = mock_client.complete.call_args[1]
        assert "system" in call_kwargs
        assert "user" in call_kwargs
        # The user prompt should contain image descriptions
        assert "MMLU" in call_kwargs["user"] or "benchmark" in call_kwargs["user"]
