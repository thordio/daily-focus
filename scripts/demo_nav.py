#!/usr/bin/env python3
"""Generate 3-day demo with working prev/next navigation.

Two-pass: first write all files, then rewrite with cross-links resolved.
"""
import asyncio, json, random, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from src.scrapers.market_data import fetch_all
from src.ai.summarizer import DailySummarizer
from src.renderer import DailyRenderer
from src.models import ContentItem, SourceType


def build_items(day, date_str):
    items = []
    for j in range(8):
        title = f"News {j + 1} on {date_str}"
        item = ContentItem(
            id=f"rss:t:{date_str}:{j}", source_type=SourceType.RSS, title=title,
            url="https://example.com", author="t", published_at=day, content="t",
            ai_score=9.0 - j * 0.3, ai_reason="t", ai_summary="t", ai_tags=["ai-tech"],
        )
        item.metadata.update({
            "topic": "ai-tech", "feed_name": "t",
            "whats_new_zh": title, "why_it_matters_zh": "m",
            "key_details_zh": "d", "background_zh": "b",
            "community_discussion_zh": "d",
            "sources": [{"url": "x", "title": title}],
        })
        items.append(item)
    return items


def build_history(market_data, day):
    history = {"version": 1, "indicators": sorted(market_data.keys()), "history": {}}
    for d_ago in range(30, -1, -1):
        d = (day - timedelta(days=d_ago)).strftime("%Y-%m-%d")
        snap = {
            k: {"price": round(v["price"] * (1 + (random.random() - 0.5) * 0.03), 2)}
            for k, v in market_data.items() if "price" in v and v["price"] is not None
        }
        if snap:
            history["history"][d] = snap
    return history


def compute_urls(daily_dir, day):
    date_str = day.strftime("%Y-%m-%d")
    yesterday = (day - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow = (day + timedelta(days=1)).strftime("%Y-%m-%d")
    prev_url = f"{yesterday}-morning-zh.html" if (daily_dir / f"{yesterday}-morning-zh.html").exists() else None
    next_url = f"{tomorrow}-morning-zh.html" if (daily_dir / f"{tomorrow}-morning-zh.html").exists() else None
    return date_str, prev_url, next_url


async def main():
    market_data = await fetch_all()
    with open("data/market-indicators.json") as f:
        meta = json.load(f)
    daily_dir = Path("docs/daily")
    daily_dir.mkdir(parents=True, exist_ok=True)

    days = [datetime.now(timezone.utc) - timedelta(days=offset) for offset in (2, 1, 0)]
    summaries = {}  # date_str -> DailySummarizer instance
    items_by_date = {d.strftime("%Y-%m-%d"): build_items(d, d.strftime("%Y-%m-%d")) for d in days}
    histories = {d.strftime("%Y-%m-%d"): build_history(market_data, d) for d in days}

    # Pass 1: write all files (without prev/next so they exist on disk)
    for day in days:
        date_str, _, _ = compute_urls(daily_dir, day)
        s = DailySummarizer()
        summaries[date_str] = s
        structured = s.get_structured_data(
            items_by_date[date_str], date_str, 50, "zh", "morning",
            score_threshold=4.0,
            market_data=market_data, market_history=histories[date_str],
            market_indicators_meta=meta,
        )
        structured["is_demo"] = True
        (daily_dir / f"{date_str}-morning-zh.html").write_text(
            DailyRenderer().render_html(structured), encoding="utf-8")

    # Pass 2: rewrite with correct prev/next cross-links
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for day in days:
        date_str, prev_url, next_url = compute_urls(daily_dir, day)
        s = summaries[date_str]
        structured = s.get_structured_data(
            items_by_date[date_str], date_str, 50, "zh", "morning",
            score_threshold=4.0,
            market_data=market_data, market_history=histories[date_str],
            market_indicators_meta=meta,
            prev_url=prev_url, next_url=next_url, latest_url="../index.html",
        )
        structured["is_demo"] = True
        fpath = daily_dir / f"{date_str}-morning-zh.html"
        fpath.write_text(DailyRenderer().render_html(structured), encoding="utf-8")
        print(f"  {fpath}  prev={prev_url}  next={next_url}")

    # Generate index.html pointing to today's report
    index_html = DailyRenderer().render_index(f"daily/{today_str}-morning-zh.html")
    (Path("docs") / "index.html").write_text(index_html, encoding="utf-8")
    print("  docs/index.html (redirects to latest)")

    latest = sorted(daily_dir.glob("*-morning-zh.html"))[-1]
    shutil.copy(latest, daily_dir / "demo-market.html")
    print(f"\nOpen: file://{latest.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
