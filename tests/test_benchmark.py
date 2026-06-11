"""Tests for the benchmark module (src/utils/benchmark.py).

Verifies that benchmarking is a no-op when disabled and works correctly
when enabled via the BENCHMARK environment variable.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.utils import benchmark as bench


# ===========================================================================
# Module-level enabled() state
# ===========================================================================


def test_benchmark_disabled_by_default():
    """enabled() returns False when BENCHMARK is not set (module default)."""
    # The module is imported without BENCHMARK env, so _ENABLED is False
    assert bench.enabled() is False


def test_benchmark_enabled_with_env(monkeypatch):
    """enabled() returns True after setting _ENABLED to True."""
    monkeypatch.setattr(bench, "_ENABLED", True)
    assert bench.enabled() is True


# ===========================================================================
# timer context manager
# ===========================================================================


def test_benchmark_timer_noop_when_disabled(monkeypatch):
    """Timer yields immediately when disabled; elapsed stays 0.0."""
    monkeypatch.setattr(bench, "_ENABLED", False)

    with bench.timer("test") as t:
        pass

    assert t.elapsed == 0.0, "Elapsed must be 0.0 when benchmarking is disabled"


# ===========================================================================
# StageTimer
# ===========================================================================


def test_benchmark_stage_timer_noop_when_disabled(monkeypatch):
    """StageTimer.record() is a no-op when benchmarking is disabled."""
    monkeypatch.setattr(bench, "_ENABLED", False)

    st = bench.StageTimer()
    st.record("fetch", 1.5, "15 items")
    assert len(st.stages) == 0, "No stages should be recorded when disabled"


def test_benchmark_stage_timer_records_when_enabled(monkeypatch):
    """StageTimer.record() appends entries when benchmarking is enabled."""
    monkeypatch.setattr(bench, "_ENABLED", True)

    st = bench.StageTimer()
    st.record("fetch", 1.5, "15 items")
    st.record("score", 3.0)
    assert len(st.stages) == 2


def test_benchmark_summary_format(monkeypatch, capsys):
    """Summary prints correct format with stage details and total."""
    monkeypatch.setattr(bench, "_ENABLED", True)

    st = bench.StageTimer()
    st.record("fetch", 1.5, "15 items")
    st.record("score", 3.0)
    st.print_summary()

    captured = capsys.readouterr()

    # Header
    assert "PIPELINE BENCHMARK SUMMARY" in captured.out
    # Stage labels
    assert "fetch" in captured.out
    assert "score" in captured.out
    # Total line
    assert "TOTAL" in captured.out
    assert "4.50" in captured.out  # 1.5 + 3.0 = 4.5
    # Separator lines
    assert "=" * 10 in captured.out


def test_benchmark_summary_empty_when_no_stages(monkeypatch, capsys):
    """print_summary produces no output when there are no recorded stages."""
    monkeypatch.setattr(bench, "_ENABLED", True)

    st = bench.StageTimer()
    st.print_summary()
    captured = capsys.readouterr()
    assert captured.out == "", "Should produce no output with no stages"


def test_benchmark_summary_noop_when_disabled(monkeypatch, capsys):
    """print_summary produces no output when benchmarking is disabled."""
    monkeypatch.setattr(bench, "_ENABLED", False)

    st = bench.StageTimer()
    st.record("fetch", 1.5, "15 items")
    st.print_summary()
    captured = capsys.readouterr()
    assert captured.out == "", "Should produce no output when disabled"
