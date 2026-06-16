"""Market data history management -- load, append, save, extract chart series."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

MARKET_KEYS = frozenset({
    "gold", "oil", "nasdaq",
    "usdcny", "eurcny", "jpycny",
    "shanghai", "chinext", "star50",
    "domestic_gold",
})


def load_history(path: Path) -> Dict[str, Any]:
    """Load market history from JSON file. Returns empty history dict on missing/corrupt file."""
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load market history: %s", exc)
    return {"version": 1, "indicators": sorted(MARKET_KEYS), "history": {}}


def append_history(
    history: Dict[str, Any],
    date_str: str,
    market_data: Dict[str, Dict],
) -> Dict[str, Any]:
    """Append a single day snapshot. Skips indicators with errors.
    Only records entries with a valid 'price' key."""
    snapshot: Dict[str, Dict] = {}
    for key in MARKET_KEYS:
        entry = market_data.get(key, {})
        if "price" in entry and entry["price"] is not None:
            snapshot[key] = {"price": entry["price"]}
    if snapshot:
        existing = history.setdefault("history", {}).setdefault(date_str, {})
        existing.update(snapshot)
    return history


def save_history(path: Path, history: Dict[str, Any]) -> None:
    """Atomic write via temp file to prevent corruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except OSError:
        logger.exception("Failed to save market history: %s", path)
        raise
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def get_chart_series(
    history: Dict[str, Any],
    indicator_key: str,
    max_days: int = 0,
) -> List[Dict[str, Any]]:
    """Extract {date, price} pairs for one indicator, sorted ascending.
    max_days=0 means all data. max_days>0 limits to last N days."""
    history_data = history.get("history", {})
    sorted_dates = sorted(history_data.keys())
    if max_days > 0 and sorted_dates:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_days)).strftime("%Y-%m-%d")
        sorted_dates = [d for d in sorted_dates if d >= cutoff]
    series = []
    for date_str in sorted_dates:
        snapshot = history_data[date_str]
        entry = snapshot.get(indicator_key)
        if entry and "price" in entry:
            series.append({"date": date_str, "price": entry["price"]})
    return series
