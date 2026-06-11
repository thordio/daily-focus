"""Lightweight pipeline benchmarking. Enable with BENCHMARK=1 env var."""
import os
import time
from contextlib import contextmanager

_ENABLED = os.environ.get("BENCHMARK", "") in ("1", "true", "yes", "on")


class _TimeResult:
    """Holds elapsed time from the timer context manager."""
    def __init__(self):
        self.elapsed: float = 0.0


@contextmanager
def live_timer(label: str):
    """Like timer() but also records to the global StageTimer for the final summary.

    Yields nothing (unlike timer() which yields a _TimeResult).
    """
    if not _ENABLED:
        yield
        return
    t0 = time.perf_counter()
    yield
    elapsed = time.perf_counter() - t0
    print(f"  ⏱ [{elapsed:6.1f}s] {label}")
    _stage_timer.record(label, elapsed)


@contextmanager
def timer(label: str, detail: str = ""):
    """Context manager that prints elapsed time when BENCHMARK is enabled.

    Yields a _TimeResult with an ``elapsed`` attribute set to the wall-clock
    time spent inside the block (0.0 when BENCHMARK is not set).
    """
    result = _TimeResult()
    if not _ENABLED:
        yield result
        return
    t0 = time.perf_counter()
    yield result
    result.elapsed = time.perf_counter() - t0
    detail_str = f" ({detail})" if detail else ""
    print(f"  ⏱ {label}: {result.elapsed:.2f}s{detail_str}")


def enabled() -> bool:
    return _ENABLED


class StageTimer:
    """Collects per-stage timing in-memory, prints summary at end."""

    def __init__(self):
        self.stages: list[tuple[str, float, str]] = []  # (label, elapsed, detail)

    def record(self, label: str, elapsed: float, detail: str = ""):
        if _ENABLED:
            self.stages.append((label, elapsed, detail))

    def print_summary(self):
        if not _ENABLED or not self.stages:
            return
        total = sum(s[1] for s in self.stages)
        print("\n" + "=" * 60)
        print("\U0001f4ca PIPELINE BENCHMARK SUMMARY")
        print("=" * 60)
        for label, elapsed, detail in self.stages:
            pct = (elapsed / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 2)
            detail_str = f" {detail}" if detail else ""
            print(f"  {label:30s} {elapsed:7.2f}s ({pct:5.1f}%) {bar}{detail_str}")
        print(f"  {'─' * 30} {'─' * 7} {'─' * 5}")
        print(f"  {'TOTAL':30s} {total:7.2f}s")
        print("=" * 60 + "\n")


# Global stage timer instance
_stage_timer = StageTimer()


def get_stage_timer() -> StageTimer:
    return _stage_timer
