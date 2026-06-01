"""HTML rendering module for Daily Focus — Jinja2 -> HTML."""

import os
from typing import List, Dict

from jinja2 import Environment, FileSystemLoader


_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


class DailyRenderer:
    """Renders structured daily data into HTML pages via Jinja2 templates."""

    def __init__(self, template_dir: str = None):
        if template_dir is None:
            template_dir = _TEMPLATE_DIR
        self._env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True,
        )
        # Register a useful filter
        self._env.filters["format_number"] = lambda v: f"{v:,}"

    def render_html(self, data: Dict) -> str:
        """Render a daily report page.

        Args:
            data: Structured data dict from ``DailySummarizer.get_structured_data()``.

        Returns:
            Complete HTML string.
        """
        tmpl = self._env.get_template("daily.html")
        return tmpl.render(**data)

    def render_archive(self, entries: List[Dict]) -> str:
        """Render the archive page listing all historical reports.

        Args:
            entries: List of dicts, each with keys:
                ``date`` (str, YYYY-MM-DD),
                ``period_label`` (str, "早报"/"晚报"/"Morning"/"Evening"),
                ``title`` (str),
                ``url`` (str, relative path).

        Returns:
            Complete HTML string.
        """
        # Group by month
        grouped = {}
        for e in entries:
            month_key = e["date"][:7]  # YYYY-MM
            if month_key not in grouped:
                grouped[month_key] = []
            grouped[month_key].append(e)

        # Sort months descending, entries within each month descending
        sorted_months = sorted(grouped.keys(), reverse=True)
        month_groups = [
            (month, sorted(grouped[month], key=lambda x: x["date"], reverse=True))
            for month in sorted_months
        ]

        tmpl = self._env.get_template("archive.html")
        return tmpl.render(entries=month_groups)

    def render_index(self, latest_url: str) -> str:
        """Render the index page that auto-redirects to the latest report.

        Args:
            latest_url: Relative URL of the latest report, e.g. ``daily/2026-06-01-morning.html``.

        Returns:
            Complete HTML string.
        """
        tmpl = self._env.get_template("index.html")
        return tmpl.render(latest_url=latest_url)
