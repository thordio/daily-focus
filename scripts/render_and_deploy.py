#!/usr/bin/env python3
"""Post-processing: rebuild docs/index.html + docs/archive.html from saved HTML.

Called by GitHub Actions AFTER `uv run horizon`.  Scans docs/daily/*.html for
daily report files, builds an archive page listing all historical reports,
and sets up index.html to redirect to the latest daily report.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional


def _parse_daily_html_path(path: Path) -> Optional[Dict[str, str]]:
    """Parse a daily HTML filename into {date, period}.

    Expected pattern::

        2026-06-01-morning.html
        2026-06-01-evening.html

    Returns None for non-matching files.
    """
    stem = path.stem
    # Date is first 10 chars: YYYY-MM-DD
    if len(stem) < 10 or stem[4] != "-" or stem[7] != "-":
        return None
    date = stem[:10]
    period = stem[11:] if len(stem) > 11 else ""
    return {"date": date, "period": period}


def _period_label(period: str) -> str:
    """Translate period key to a label for display."""
    if period == "morning":
        return "Morning"
    if period == "evening":
        return "Evening"
    return "Morning"


def build_archive_entries(daily_dir: Path) -> List[Dict[str, str]]:
    """Build archive entry dicts from all *.html files in docs/daily/.

    Returns entries sorted newest-first.  Each entry has keys:
        date, period_label, title, url
    """
    if not daily_dir.exists():
        return []

    entries: List[Dict[str, str]] = []
    for path in sorted(daily_dir.glob("*.html"), reverse=True):
        parsed = _parse_daily_html_path(path)
        if parsed is None:
            continue
        date = parsed["date"]
        period = parsed["period"]

        title = f"Daily Focus — {date}"
        period_label = _period_label(period)
        url = f"daily/{date}-{period}.html" if period else f"daily/{date}.html"
        entries.append({
            "date": date,
            "period_label": period_label,
            "title": title,
            "url": url,
        })

    return entries


def find_latest_summary(daily_dir: Path) -> Optional[Dict[str, str]]:
    """Return metadata dict for the newest HTML file, or None."""
    entries = build_archive_entries(daily_dir)
    return entries[0] if entries else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild docs/index.html + docs/archive.html from saved HTML reports."
    )
    parser.add_argument("--period", default="morning", help="Edition period")
    args = parser.parse_args()

    # Paths
    project_root = Path(__file__).resolve().parent.parent
    docs_dir = project_root / "docs"
    daily_dir = docs_dir / "daily"

    docs_dir.mkdir(parents=True, exist_ok=True)

    # Add project root to sys.path so we can import src modules
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.renderer import DailyRenderer

    renderer = DailyRenderer()

    # --- Archive page ---------------------------------------------------
    entries = build_archive_entries(daily_dir)
    archive_html = renderer.render_archive(entries)
    archive_path = docs_dir / "archive.html"
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(archive_html)
    print(f"📄 Archive: {archive_path} ({len(entries)} entries)")

    # --- Index page (redirect to latest daily report) -------------------
    latest = find_latest_summary(daily_dir)
    if latest:
        latest_url = latest["url"]
    else:
        # No reports yet — redirect to archive (will show empty state)
        latest_url = "archive.html"

    index_html = renderer.render_index(latest_url)
    index_path = docs_dir / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"📄 Index: {index_path} -> {latest_url}")


if __name__ == "__main__":
    main()
