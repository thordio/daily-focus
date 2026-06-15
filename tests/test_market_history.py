"""Tests for market_history.py — load, append, save, extract chart series."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("src.scrapers.market_history")
from src.scrapers.market_history import (
    MARKET_KEYS,
    append_history,
    get_chart_series,
    load_history,
    save_history,
)

SAMPLE_HISTORY = {
    "version": 1,
    "indicators": sorted(MARKET_KEYS),
    "history": {
        "2026-06-01": {"gold": {"price": 2350.0}, "oil": {"price": 78.0}},
        "2026-06-02": {"gold": {"price": 2355.0}, "oil": {"price": 77.5}},
        "2026-06-03": {"gold": {"price": 2360.0}},
    },
}

SAMPLE_DATA = {
    "gold": {"price": 2365.0},
    "oil": {"price": 78.5},
    "nasdaq": {"price": 19800.0},
    "usdcny": {"price": 7.25},
    "eurcny": {"price": 7.79},
    "jpycny": {"error": "timeout"},
    "shanghai": {"price": 3200.0},
    "chinext": {"price": 2100.0},
    "star50": {"price": 990.0},
    "domestic_gold": {"price": 550.12},
}


class TestLoadHistory:
    def test_load_existing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "history.json"
        p.write_text(json.dumps(SAMPLE_HISTORY))
        result = load_history(p)
        assert result["version"] == 1
        assert "2026-06-01" in result["history"]

    def test_load_missing_file_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.json"
        result = load_history(p)
        assert result["version"] == 1
        assert result["history"] == {}
        assert result["indicators"] == sorted(MARKET_KEYS)

    def test_load_corrupted_json_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.json"
        p.write_text("{not valid json")
        result = load_history(p)
        assert result["history"] == {}

    def test_load_empty_file_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.json"
        p.write_text("")
        result = load_history(p)
        assert result["history"] == {}


class TestAppendHistory:
    def test_append_new_date(self) -> None:
        history = {"version": 1, "indicators": sorted(MARKET_KEYS), "history": {}}
        result = append_history(history, "2026-06-15", SAMPLE_DATA)
        assert "2026-06-15" in result["history"]
        assert result["history"]["2026-06-15"]["gold"]["price"] == 2365.0
        assert result["history"]["2026-06-15"]["nasdaq"]["price"] == 19800.0

    def test_skips_error_indicators(self) -> None:
        history = {"version": 1, "indicators": sorted(MARKET_KEYS), "history": {}}
        result = append_history(history, "2026-06-15", SAMPLE_DATA)
        # jpycny has "error", should not be in snapshot
        assert "jpycny" not in result["history"]["2026-06-15"]

    def test_skips_none_price(self) -> None:
        data = {"gold": {"price": None}, "oil": {"price": 77.0}}
        history = {"version": 1, "indicators": sorted(MARKET_KEYS), "history": {}}
        result = append_history(history, "2026-06-15", data)
        assert "gold" not in result["history"]["2026-06-15"]
        assert result["history"]["2026-06-15"]["oil"]["price"] == 77.0

    def test_overwrites_existing_date(self) -> None:
        history = {
            "version": 1,
            "indicators": sorted(MARKET_KEYS),
            "history": {"2026-06-15": {"gold": {"price": 2300.0}}},
        }
        result = append_history(history, "2026-06-15", {"gold": {"price": 2365.0}})
        assert result["history"]["2026-06-15"]["gold"]["price"] == 2365.0

    def test_no_snapshot_when_all_errors(self) -> None:
        history = {"version": 1, "indicators": sorted(MARKET_KEYS), "history": {}}
        data = {k: {"error": "fail"} for k in MARKET_KEYS}
        result = append_history(history, "2026-06-15", data)
        assert "2026-06-15" not in result["history"]

    def test_returns_same_dict(self) -> None:
        """append_history mutates and returns the same dict."""
        history = {"version": 1, "indicators": sorted(MARKET_KEYS), "history": {}}
        result = append_history(history, "2026-06-15", SAMPLE_DATA)
        assert result is history


class TestSaveHistory:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        p = tmp_path / "subdir" / "history.json"
        save_history(p, SAMPLE_HISTORY)
        assert p.exists()

    def test_save_and_reload_roundtrip(self, tmp_path: Path) -> None:
        p = tmp_path / "history.json"
        save_history(p, SAMPLE_HISTORY)
        reloaded = json.loads(p.read_text())
        assert reloaded == SAMPLE_HISTORY

    def test_save_is_valid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "history.json"
        save_history(p, SAMPLE_HISTORY)
        # Should not raise
        json.loads(p.read_text())

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        p = tmp_path / "history.json"
        old = {"version": 1, "indicators": [], "history": {"2020-01-01": {}}}
        p.write_text(json.dumps(old))
        save_history(p, SAMPLE_HISTORY)
        reloaded = json.loads(p.read_text())
        assert reloaded == SAMPLE_HISTORY


class TestGetChartSeries:
    def test_all_days(self) -> None:
        series = get_chart_series(SAMPLE_HISTORY, "gold")
        assert len(series) == 3
        assert series[0] == {"date": "2026-06-01", "price": 2350.0}
        assert series[-1] == {"date": "2026-06-03", "price": 2360.0}

    def test_limited_days_filters_correctly(self) -> None:
        """max_days=2 should only return the last 2 days of data."""
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")

        data = {
            "version": 1, "indicators": ["gold"],
            "history": {
                three_days_ago: {"gold": {"price": 100.0}},
                yesterday: {"gold": {"price": 200.0}},
                today: {"gold": {"price": 300.0}},
            }
        }
        series = get_chart_series(data, "gold", max_days=2)
        # Should include yesterday and today (last 2 days), but NOT three_days_ago
        assert len(series) == 2
        assert series[0]["date"] == yesterday
        assert series[-1]["date"] == today

    def test_missing_indicator(self) -> None:
        series = get_chart_series(SAMPLE_HISTORY, "nonexistent")
        assert series == []

    def test_indicator_missing_on_some_dates(self) -> None:
        """oil is only in first 2 days of SAMPLE_HISTORY."""
        series = get_chart_series(SAMPLE_HISTORY, "oil")
        assert len(series) == 2

    def test_empty_history(self) -> None:
        empty = {"version": 1, "indicators": [], "history": {}}
        series = get_chart_series(empty, "gold")
        assert series == []

    def test_results_sorted_by_date(self) -> None:
        series = get_chart_series(SAMPLE_HISTORY, "gold")
        dates = [p["date"] for p in series]
        assert dates == sorted(dates)

    def test_max_days_zero_returns_all(self) -> None:
        series = get_chart_series(SAMPLE_HISTORY, "gold", max_days=0)
        assert len(series) == 3
