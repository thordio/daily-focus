#!/usr/bin/env python3
"""Post-processing: rebuild docs/index.html + docs/archive.html from saved summaries.

Called by GitHub Actions AFTER `uv run horizon`.  Scans data/summaries/ for
markdown summary files, builds an archive page listing all historical reports,
and sets up index.html to redirect to the latest daily report.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


def _parse_summary_path(path: Path) -> Optional[Dict[str, str]]:
    """Parse a summary filename into {date, lang, period}.

    Expected patterns::

        horizon-2026-06-01-zh-morning.md
        horizon-2026-06-01-zh.md            (legacy, no period)

    Returns None for non-matching files.
    """
    stem = path.stem
    parts = stem.split("-")
    # parts[0] must be "horizon"
    if len(parts) < 4 or parts[0] != "horizon":
        return None
    date = "-".join(parts[1:4])
    if len(parts) >= 5:
        lang = parts[4]
        period = parts[5] if len(parts) >= 6 else ""
    else:
        lang = parts[4] if len(parts) >= 5 else "en"
        period = ""
    return {"date": date, "lang": lang, "period": period}


def _period_label(period: str, fallback: str = "Morning") -> str:
    """Translate period key to a label for display."""
    if not period:
        return fallback
    if period == "morning":
        return "早报" if fallback == "zh" else "Morning"
    return "晚报" if fallback == "zh" else "Evening"


def build_archive_entries(
    summaries_dir: Path,
) -> List[Dict[str, str]]:
    """Build archive entry dicts from all horizon-*.md summary files.

    Returns entries sorted newest-first.  Each entry has keys:
        date, period_label, title, url
    """
    if not summaries_dir.exists():
        return []

    entries: List[Dict[str, str]] = []
    for path in sorted(summaries_dir.glob("horizon-*.md"), reverse=True):
        parsed = _parse_summary_path(path)
        if parsed is None:
            continue
        date = parsed["date"]
        period = parsed["period"]

        # Attempt to read a title from the first line of the markdown
        title = f"Daily Focus — {date}"
        try:
            first_line = path.read_text(encoding="utf-8").strip().split("\n")[0]
            title = first_line.lstrip("# ").strip() or title
        except OSError:
            pass

        periods_display = _period_label(period, parsed["lang"])
        url = f"daily/{date}-{period}.html" if period else f"daily/{date}.html"
        entries.append({
            "date": date,
            "period_label": periods_display,
            "title": title,
            "url": url,
        })

    return entries


def find_latest_summary(summaries_dir: Path) -> Optional[Dict[str, str]]:
    """Return metadata dict for the newest summary file, or None."""
    entries = build_archive_entries(summaries_dir)
    return entries[0] if entries else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild docs/index.html + docs/archive.html from saved summaries."
    )
    parser.add_argument("--period", default="morning", help="Edition period")
    args = parser.parse_args()

    # Paths
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    docs_dir = project_root / "docs"
    summaries_dir = data_dir / "summaries"

    docs_dir.mkdir(parents=True, exist_ok=True)

    # Add project root to sys.path so we can import src modules
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.renderer import DailyRenderer

    renderer = DailyRenderer()

    # --- Archive page ---------------------------------------------------
    entries = build_archive_entries(summaries_dir)
    archive_html = renderer.render_archive(entries)
    archive_path = docs_dir / "archive.html"
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(archive_html)
    print(f"📄 Archive: {archive_path} ({len(entries)} entries)")

    # --- Index page (redirect to latest daily report) -------------------
    latest = find_latest_summary(summaries_dir)
    if latest:
        latest_url = latest["url"]
    else:
        # No summaries yet — redirect to archive (will show empty state)
        latest_url = "archive.html"

    index_html = renderer.render_index(latest_url)
    index_path = docs_dir / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"📄 Index: {index_path} -> {latest_url}")


if __name__ == "__main__":
    main()
