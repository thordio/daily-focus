"""Tests for market_data.py — 10 market indicator fetcher.

Test strategy
-------------
- Unit tests (fast, no network): mock the three sub-fetchers
  (``fetch_forex``, ``fetch_sina``, ``fetch_us_indices``) and verify
  that ``fetch_all`` correctly aggregates and structures results.
- Integration tests (real APIs): call ``fetch_all``, ``fetch_forex``,
  ``fetch_sina`` or ``fetch_us_indices`` directly and check the results
  for reasonableness.
- Slow / integration tests are marked so they can be skipped in CI.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("src.scrapers.market_data")

from src.scrapers.market_data import fetch_all

# ── Constants ────────────────────────────────────────────────────────

EXPECTED_KEYS = frozenset({
    "gold", "oil", "nasdaq",
    "usdcny", "usdjpy", "eurusd",
    "shanghai", "chinext", "star50",
})

# Realistic mock data for the three sub-fetchers.
MOCK_FOREX = {
    "usdcny": {"price": 7.2456},
    "usdjpy": {"price": 151.30},
    "eurusd": {"price": 1.0842},
}

MOCK_SINA = {
    "shanghai": {"price": 3150.45},
    "chinext": {"price": 2050.30},
    "star50": {"price": 980.60},
    "gold": {"price": 2350.80},
    "oil": {"price": 78.45},
}

MOCK_US = {
    "nasdaq": {"price": 18500.75},
}


# ── Helpers ──────────────────────────────────────────────────────────

def _patch_fetchers(forex_return, sina_return, us_return):
    """Context-manager helper that patches the three sub-fetchers.

    Each mock is an ``AsyncMock`` so that ``asyncio.gather`` inside
    ``fetch_all`` can ``await`` them.
    """
    return (
        patch("src.scrapers.market_data.fetch_forex", AsyncMock(return_value=forex_return)),
        patch("src.scrapers.market_data.fetch_sina", AsyncMock(return_value=sina_return)),
        patch("src.scrapers.market_data.fetch_nasdaq", AsyncMock(return_value=us_return)),
    )


def _run_fetch_all_mocked(mock_data: tuple[dict, dict, dict]) -> dict:
    """Run ``fetch_all`` with the three sub-fetchers replaced by mocks.

    ``mock_data`` is ``(forex_return, sina_return, us_return)``.
    """
    forex, sina, us = mock_data
    patches = _patch_fetchers(forex, sina, us)
    with patches[0], patches[1], patches[2]:
        return asyncio.run(fetch_all())


# ─────────────────────────────────────────────────────────────────────
# Unit tests (mocked sub-fetchers)
# ─────────────────────────────────────────────────────────────────────


class TestFetchAllInterface:
    """Tests for the ``fetch_all`` public interface with mocked internals."""

    def test_fetch_all_returns_9_indicators(self):
        """fetch_all() returns a dict with all 9 expected indicator keys."""
        result = _run_fetch_all_mocked((MOCK_FOREX, MOCK_SINA, MOCK_US))

        assert isinstance(result, dict)
        assert len(result) == 9
        missing = EXPECTED_KEYS - result.keys()
        assert not missing, f"Missing indicator keys: {missing}"

    def test_fetch_all_price_structure(self):
        """Every indicator value has a ``price`` field (float, int, or None)."""
        result = _run_fetch_all_mocked((MOCK_FOREX, MOCK_SINA, MOCK_US))

        for key, value in result.items():
            assert "price" in value, f"{key} entry missing 'price' field"
            price = value["price"]
            if price is not None:
                assert isinstance(price, (int, float)), (
                    f"{key}.price should be int, float, or None, "
                    f"got {type(price).__name__}"
                )

    def test_fetch_all_returns_9_even_with_errors(self):
        """fetch_all returns 10 entries even when some sub-fetchers have errors."""
        result = _run_fetch_all_mocked((
            {k: {"error": "timeout"} for k in ("usdcny", "usdjpy", "eurusd")},
            MOCK_SINA,
            MOCK_US,
        ))

        assert len(result) == 9
        assert "error" in result["usdcny"]
        assert "price" in result["shanghai"]
        assert "price" in result["nasdaq"]


class TestPartialFailure:
    """One sub-fetcher failing should not prevent the others from returning."""

    def test_forex_failure_preserves_sina_and_us(self):
        """Forex errors: sina and US data still returned."""
        result = _run_fetch_all_mocked((
            {k: {"error": "Forex API down"} for k in ("usdcny", "usdjpy", "eurusd")},
            MOCK_SINA,
            MOCK_US,
        ))

        assert result["usdcny"].get("error") is not None
        assert result["shanghai"]["price"] == MOCK_SINA["shanghai"]["price"]
        assert result["nasdaq"]["price"] == MOCK_US["nasdaq"]["price"]

    def test_sina_failure_preserves_forex_and_us(self):
        """Sina errors: forex and US data still returned."""
        result = _run_fetch_all_mocked((
            MOCK_FOREX,
            {k: {"error": "Sina API down"} for k in MOCK_SINA},
            MOCK_US,
        ))

        assert result["shanghai"].get("error") is not None
        assert result["usdcny"]["price"] == MOCK_FOREX["usdcny"]["price"]
        assert result["nasdaq"]["price"] == MOCK_US["nasdaq"]["price"]

    def test_us_failure_preserves_forex_and_sina(self):
        """US indices errors: forex and sina data still returned."""
        result = _run_fetch_all_mocked((
            MOCK_FOREX,
            MOCK_SINA,
            {k: {"error": "akshare error"} for k in MOCK_US},
        ))

        assert result["nasdaq"].get("error") is not None
        assert result["usdcny"]["price"] == MOCK_FOREX["usdcny"]["price"]
        assert result["shanghai"]["price"] == MOCK_SINA["shanghai"]["price"]


# ─────────────────────────────────────────────────────────────────────
# Integration tests (real API calls, marked so CI can skip them)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestForexIntegration:
    """Integration tests for forex exchange-rate endpoints."""

    def test_fetch_forex_prices_reasonable(self):
        """Forex prices in expected ranges: CNY 5-8, JPY 100-200, EUR 0.8-1.5."""
        try:
            from src.scrapers.market_data import fetch_forex
        except ImportError:
            pytest.skip("fetch_forex not available in market_data module")

        result = asyncio.run(fetch_forex())

        assert "usdcny" in result
        assert "usdjpy" in result
        assert "eurusd" in result

        cny = result["usdcny"].get("price")
        if cny is not None:
            assert 5.0 <= cny <= 8.0, f"USD/CNY {cny} outside expected range 5.0-8.0"

        jpy = result["usdjpy"].get("price")
        if jpy is not None:
            assert 100.0 <= jpy <= 200.0, f"USD/JPY {jpy} outside expected range 100-200"

        eur = result["eurusd"].get("price")
        if eur is not None:
            assert 0.8 <= eur <= 1.5, f"EUR/USD {eur} outside expected range 0.8-1.5"


@pytest.mark.integration
class TestSinaIntegration:
    """Integration tests for Sina finance endpoints."""

    def test_fetch_sina_prices_reasonable(self):
        """Sina prices in expected ranges: Shanghai 2500-5000, gold 1000-5000, oil 50-150."""
        try:
            from src.scrapers.market_data import fetch_sina
        except ImportError:
            pytest.skip("fetch_sina not available in market_data module")

        result = asyncio.run(fetch_sina())

        assert "shanghai" in result
        assert "gold" in result
        assert "oil" in result

        sh = result["shanghai"].get("price")
        if sh is not None:
            assert 2500.0 <= sh <= 5000.0, (
                f"Shanghai Composite {sh} outside expected range 2500-5000"
            )

        gold = result["gold"].get("price")
        if gold is not None:
            assert 1000.0 <= gold <= 5000.0, (
                f"Gold {gold} outside expected range 1000-5000"
            )

        oil = result["oil"].get("price")
        if oil is not None:
            assert 50.0 <= oil <= 150.0, (
                f"Crude Oil {oil} outside expected range 50-150"
            )


@pytest.mark.integration
class TestUSIndicesIntegration:
    """Integration tests for NASDAQ via akshare."""

    def test_fetch_nasdaq_price_reasonable(self):
        """NASDAQ price is between 10 000 and 30 000."""
        try:
            import akshare  # noqa: F401
        except ImportError:
            pytest.skip("akshare not installed")
        try:
            from src.scrapers.market_data import fetch_nasdaq
        except ImportError:
            pytest.skip("fetch_nasdaq not available")

        result = asyncio.run(fetch_nasdaq())
        price = result.get("nasdaq", {}).get("price")
        if price is None:
            pytest.skip(f"NASDAQ price unavailable: {result.get('nasdaq', {})}")
        assert 10000.0 <= price <= 30000.0, (
            f"NASDAQ {price} outside expected range 10000-30000"
        )

@pytest.mark.slow
class TestTimeout:
    """End-to-end timing test for fetch_all."""

    def test_fetch_all_within_timeout(self):
        """fetch_all completes in under 60 seconds."""
        start = time.monotonic()
        result = asyncio.run(fetch_all())
        elapsed = time.monotonic() - start

        assert elapsed < 60.0, (
            f"fetch_all took {elapsed:.1f}s, expected < 60s"
        )
        assert len(result) == 9
