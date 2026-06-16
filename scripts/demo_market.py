#!/usr/bin/env python3
"""Generate a demo HTML page with all 4 tabs (3 news + market indicators)
and working prev/next day navigation.

Two-pass: first write all files, then rewrite with cross-links resolved.
"""
import asyncio
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.scrapers.market_data import fetch_all
from src.ai.summarizer import DailySummarizer
from src.renderer import DailyRenderer
from src.models import ContentItem, SourceType


def build_items(day: datetime, date_str: str) -> list[ContentItem]:
    """Build demo news items for a given date."""
    topics = [
        ("ai-tech", [
            ("OpenAI GPT-5 发布", "https://openai.com", 9.2),
            ("DeepSeek V4 开源", "https://deepseek.com", 8.8),
            ("AlphaFold 4 发布", "https://deepmind.google", 8.5),
            ("Claude Code 2.0", "https://anthropic.com", 8.3),
            ("Llama 5 开源", "https://ai.meta.com", 7.9),
            ("B300 GPU 发布", "https://nvidia.com", 7.5),
            ("Stable Video 开源", "https://stability.ai", 7.2),
            ("Copilot 全面集成", "https://microsoft.com", 6.8),
        ]),
        ("ai-markets", [
            ("NVIDIA 市值 5万亿", "https://nvidia.com", 9.0),
            ("Groq 融资 30亿", "https://groq.com", 8.5),
            ("OpenAI 估值 5000亿", "https://openai.com", 8.2),
            ("台积电 2nm 量产", "https://tsmc.com", 7.8),
            ("AI SaaS 增长 240%", "https://example.com", 7.5),
            ("ARM AI 架构发布", "https://arm.com", 7.0),
        ]),
        ("economy", [
            ("美联储维持利率", "https://federalreserve.gov", 8.8),
            ("中国 GDP 5.2%", "https://stats.gov.cn", 8.5),
            ("欧央行降息", "https://ecb.europa.eu", 7.8),
            ("日本结束负利率", "https://boj.or.jp", 7.5),
            ("供应链压力新低", "https://example.com", 6.5),
        ]),
    ]
    items: list[ContentItem] = []
    idx = 0
    for topic_key, articles in topics:
        for title, url, score in articles:
            idx += 1
            item = ContentItem(
                id=f"rss:{topic_key}:{idx}",
                source_type=SourceType.RSS,
                title=title,
                url=url,
                author="source",
                published_at=day - timedelta(hours=(idx * 7) % 23 + 1),
                content=f"{title} 详细内容",
                ai_score=score,
                ai_reason="重要事件",
                ai_summary=f"{title} 摘要",
                ai_tags=[topic_key],
            )
            item.metadata.update({
                "topic": topic_key, "feed_name": "source",
                "whats_new_zh": f"【{title}】最新进展。",
                "why_it_matters_zh": f"对{topic_key}领域产生重要影响。",
                "key_details_zh": "关键数据支撑判断。",
                "background_zh": "持续布局。",
                "community_discussion_zh": "社区讨论热烈。",
                "sources": [{"url": url, "title": title}],
            })
            items.append(item)
    return items


async def main() -> None:
    print("Fetching market data...")
    market_data = await fetch_all()
    ok = sum(1 for v in market_data.values() if "price" in v)
    print(f"  Market: {ok}/{len(market_data)} indicators OK")

    with open("data/market-indicators.json") as f:
        meta = json.load(f)

    daily_dir = Path("docs/daily")
    daily_dir.mkdir(parents=True, exist_ok=True)

    # Load REAL market history (June 15 extracted from live + June 16 from API)
    history_path = daily_dir / "market-history.json"
    if history_path.exists():
        with open(history_path) as f:
            real_history = json.load(f)
        print(f"  History: {len(real_history.get('history', {}))} real dates loaded")
    else:
        real_history = {"version": 1, "indicators": sorted(market_data.keys()), "history": {}}

    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    # 3 consecutive days so prev/next links resolve locally
    days = [today - timedelta(days=offset) for offset in (2, 1, 0)]

    # Enrich prev_close from REAL history (so percentage badges render)
    yesterday_history = real_history.get("history", {}).get(yesterday, {})
    for key, entry in market_data.items():
        if "price" in entry and entry.get("prev_close") is None:
            if key in yesterday_history:
                entry["prev_close"] = yesterday_history[key]["price"]

    items_by_date: dict[str, list[ContentItem]] = {}
    for day in days:
        date_str = day.strftime("%Y-%m-%d")
        items_by_date[date_str] = build_items(day, date_str)

    # Pass 1: write all files (without prev/next so they exist on disk)
    print("\nPass 1 — writing all 3 files...")
    for day in days:
        date_str = day.strftime("%Y-%m-%d")
        structured = DailySummarizer().get_structured_data(
            items_by_date[date_str], date_str, len(items_by_date[date_str]),
            language="zh", period="morning", score_threshold=4.0,
            market_data=market_data, market_history=real_history,
            market_indicators_meta=meta,
        )
        structured["is_demo"] = True
        fpath = daily_dir / f"{date_str}-morning-zh.html"
        fpath.write_text(DailyRenderer().render_html(structured), encoding="utf-8")
        print(f"  {fpath.name}")

    # Pass 2: rewrite with correct prev/next cross-links
    print("\nPass 2 — setting cross-links...")
    for day in days:
        date_str = day.strftime("%Y-%m-%d")
        yesterday = (day - timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow = (day + timedelta(days=1)).strftime("%Y-%m-%d")
        prev_path = daily_dir / f"{yesterday}-morning-zh.html"
        next_path = daily_dir / f"{tomorrow}-morning-zh.html"
        prev_url = prev_path.name if prev_path.exists() else None
        next_url = next_path.name if next_path.exists() else None

        structured = DailySummarizer().get_structured_data(
            items_by_date[date_str], date_str, len(items_by_date[date_str]),
            language="zh", period="morning", score_threshold=4.0,
            market_data=market_data, market_history=real_history,
            market_indicators_meta=meta,
            prev_url=prev_url, next_url=next_url, latest_url="../index.html",
        )
        structured["is_demo"] = True
        fpath = daily_dir / f"{date_str}-morning-zh.html"
        fpath.write_text(DailyRenderer().render_html(structured), encoding="utf-8")
        print(f"  {fpath.name}  prev={prev_url}  next={next_url}")

    # Generate index.html redirecting to today's report
    index_html = DailyRenderer().render_index(f"daily/{today_str}-morning-zh.html")
    (Path("docs") / "index.html").write_text(index_html, encoding="utf-8")
    print("  docs/index.html")

    # Copy today's file as the canonical demo
    shutil.copy(daily_dir / f"{today_str}-morning-zh.html", daily_dir / "demo-market.html")
    print(f"\nDone: {daily_dir / 'demo-market.html'}")
    print(f"Open: file://{(daily_dir / 'demo-market.html').resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
