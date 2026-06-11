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
    """Parse a daily HTML filename into {date, period, lang}.

    Expected patterns::

        2026-06-01.html                    (no lang, no period)
        2026-06-01-zh.html                 (lang, no period — new single-edition)
        2026-06-01-morning.html            (no lang — legacy two-edition)
        2026-06-01-morning-zh.html         (with lang code — legacy two-edition)

    Returns None for non-matching files.
    """
    stem = path.stem
    parts = stem.split("-")
    # parts: [YYYY, MM, DD] or [YYYY, MM, DD, period/lang] or [YYYY, MM, DD, period, lang]
    if len(parts) < 3 or len(parts) > 5:
        return None
    date = "-".join(parts[:3])
    if len(date) != 10 or date[4] != "-" or date[7] != "-":
        return None
    period: str | None = None
    lang: str | None = None
    if len(parts) == 4:
        fourth = parts[3]
        if fourth in ("morning", "evening"):
            period = fourth
        else:
            lang = fourth
    elif len(parts) == 5:
        period = parts[3]
        lang = parts[4]
    return {"date": date, "period": period, "lang": lang}


def _period_label(period: str | None) -> str:
    """Translate period key to a label for display. Returns '' for single-edition (no period)."""
    if period is None:
        return ""
    return "Morning" if period == "morning" else "Evening"


def build_archive_entries(daily_dir: Path) -> List[Dict[str, str]]:
    """Build archive entry dicts from all *.html files in docs/daily/.

    Returns entries sorted newest-first.  Each entry has keys:
        date, period_label, title, url

    When both ``zh`` and ``en`` versions exist for the same date+period,
    only one entry is emitted (preferring ``zh``, the default language).
    """
    if not daily_dir.exists():
        return []

    raw: list[dict] = []
    for path in daily_dir.glob("*.html"):
        parsed = _parse_daily_html_path(path)
        if parsed is None:
            continue
        date = parsed["date"]
        period = parsed["period"]
        lang = parsed.get("lang")  # None for legacy files (no language suffix)
        if period and lang:
            url = f"daily/{date}-{period}-{lang}.html"
        elif period:
            url = f"daily/{date}-{period}.html"
        elif lang:
            url = f"daily/{date}-{lang}.html"
        else:
            url = f"daily/{date}.html"
        raw.append({
            "date": date,
            "period": period,
            "period_label": _period_label(period),
            "title": f"Daily Focus — {date}",
            "url": url,
            "lang": lang,
        })

    # Deduplicate by (date, period), preferring zh over en
    best: dict[tuple[str, str], dict] = {}
    for e in raw:
        key = (e["date"], e["period"])
        # zh is the default/primary language; prefer it
        if key not in best or (e["lang"] == "zh" and best[key]["lang"] != "zh"):
            best[key] = e

    # Sort newest-first by date, then morning before evening within same date
    entries = sorted(
        best.values(),
        key=lambda x: (x["date"], {"morning": 0, "evening": 1}.get(x["period"], 0)),
        reverse=True,
    )
    return entries


def find_latest_summary(daily_dir: Path) -> Optional[Dict[str, str]]:
    """Return metadata dict for the newest HTML file, or None."""
    entries = build_archive_entries(daily_dir)
    return entries[0] if entries else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild docs/index.html + docs/archive.html from saved HTML reports."
    )
    parser.add_argument("--period", default=None, help="Edition period (deprecated, kept for backward compat)")
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
