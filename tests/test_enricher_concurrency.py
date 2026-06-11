"""Concurrency tests for ContentEnricher.

Verifies that:
1. _get_concurrency() respects the configured value with proper clamping
2. Concurrent execution actually processes items in parallel (not serially)
"""

from __future__ import annotations

import asyncio
import copy
import time
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from src.ai.enricher import ContentEnricher
from tests.conftest_helpers import make_content_item


MOCK_RESPONSE = '{"whats_new_en": "test content.", "why_it_matters_en": "test reason."}'


# ---------------------------------------------------------------------------
# Test 1: _get_concurrency() respects config value with proper clamping
# ---------------------------------------------------------------------------

def test_enricher_respects_concurrency_setting():
    """Verify _get_concurrency returns configured value, clamped to >= 1.

    This tests the pipeline that feeds ``asyncio.Semaphore(concurrency)``
    inside ``enrich_batch`` — if this returns the wrong value, the semaphore
    does not correctly limit or enable parallelism.
    """
    mock_client = AsyncMock()
    mock_client.complete.return_value = MOCK_RESPONSE

    # Case 1: normal concurrency=5
    mock_client.config = MagicMock(enrichment_concurrency=5, languages=["en"])
    enricher = ContentEnricher(mock_client)
    assert enricher._get_concurrency() == 5, "_get_concurrency() should return 5"

    # Case 2: concurrency=0 should clamp to 1
    mock_client.config.enrichment_concurrency = 0
    assert enricher._get_concurrency() == 1, "concurrency=0 must clamp to 1"

    # Case 3: concurrency=-1 should clamp to 1
    mock_client.config.enrichment_concurrency = -1
    assert enricher._get_concurrency() == 1, "concurrency=-1 must clamp to 1"

    # Case 4: concurrency=1 (minimum valid)
    mock_client.config.enrichment_concurrency = 1
    assert enricher._get_concurrency() == 1, "concurrency=1 should stay as 1"

    # Case 5: no enrichment_concurrency attribute at all → default to 1
    mock_no_config = AsyncMock()
    mock_no_config.config = MagicMock(spec=[])  # empty spec: no enrichment_concurrency
    mock_no_config.complete.return_value = MOCK_RESPONSE
    enricher_default = ContentEnricher(mock_no_config)
    assert enricher_default._get_concurrency() == 1, (
        "No enrichment_concurrency must default to 1"
    )


# ---------------------------------------------------------------------------
# Test 2: Concurrent execution is measurably faster than serial
# ---------------------------------------------------------------------------

def test_enricher_concurrent_execution():
    """Verify items are processed concurrently (not serially).

    Uses a mock AI call that sleeps 100ms per item. With concurrency=5 and
    10 items the expected wall time is ~200ms (ceil(10/5) * 100ms) while
    serial processing would take ~1000ms. The test asserts concurrent time
    is significantly less than the serial estimate.
    """
    delay = 0.1  # 100ms per item

    async def mock_complete(system, user, temperature=None, max_tokens=None):
        await asyncio.sleep(delay)
        return MOCK_RESPONSE

    mock_client = AsyncMock()
    mock_client.complete.side_effect = mock_complete
    mock_client.config = MagicMock(enrichment_concurrency=5, languages=["en"])

    items = [
        make_content_item(
            item_id=f"item-{i}",
            title=f"Item {i}",
            ai_score=8.5,
            content=f"Content of item {i}.",
            ai_summary=f"Summary {i}.",
            ai_reason=f"Reason {i}.",
            ai_tags=["test"],
        )
        for i in range(10)
    ]

    enricher = ContentEnricher(mock_client)
    enricher._web_search = AsyncMock(return_value=[])

    # Measure concurrent execution (concurrency=5, 10 items)
    start = time.perf_counter()
    asyncio.run(enricher.enrich_batch(copy.deepcopy(items)))
    concurrent_time = time.perf_counter() - start

    # Serial estimate: each item takes delay seconds, processed one at a time
    serial_estimate = delay * 10  # 1.0s

    # Concurrent estimate: ceil(10/5) * delay = 0.2s
    # Actual measured time should be well under 80% of serial estimate
    assert concurrent_time < serial_estimate * 0.75, (
        f"Concurrent execution ({concurrent_time:.3f}s) not sufficiently faster "
        f"than serial estimate ({serial_estimate:.3f}s). "
        f"Expected ~{serial_estimate / 5:.3f}s if truly concurrent with {delay}s/item."
    )

    # Also run with concurrency=1 to confirm it's slower than concurrency=5
    mock_client.config.enrichment_concurrency = 1
    enricher_serial = ContentEnricher(mock_client)
    enricher_serial._web_search = AsyncMock(return_value=[])

    start = time.perf_counter()
    asyncio.run(enricher_serial.enrich_batch(copy.deepcopy(items)))
    serial_time = time.perf_counter() - start

    # Concurrent (concurrency=5) should be significantly faster than serial (concurrency=1)
    assert concurrent_time < serial_time * 0.7, (
        f"Concurrency=5 ({concurrent_time:.3f}s) not faster than "
        f"concurrency=1 ({serial_time:.3f}s). Items are not processing concurrently."
    )
