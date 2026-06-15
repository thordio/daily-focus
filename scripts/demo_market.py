#!/usr/bin/env python3
"""Generate a demo HTML page with all 4 tabs (3 news + market indicators)."""
import asyncio
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.scrapers.market_data import fetch_all
from src.ai.summarizer import DailySummarizer
from src.renderer import DailyRenderer
from src.models import ContentItem, SourceType


async def main() -> None:
    print("Fetching market data...")
    market_data = await fetch_all()
    ok = sum(1 for v in market_data.values() if "price" in v)
    print(f"  Market: {ok}/{len(market_data)} indicators OK")

    with open("data/market-indicators.json") as f:
        meta = json.load(f)

    # Build simulated history: 1 day (today only) + 30-day option
    # Set to 30 for full demo, 0 for single-point test
    HISTORY_DAYS = 30  # change to 0 for single-point test
    today = datetime.now(timezone.utc)
    history: dict = {"version": 1, "indicators": sorted(market_data.keys()), "history": {}}
    for days_ago in range(HISTORY_DAYS, -1, -1):
        d = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        snapshot: dict = {}
        for key, val in market_data.items():
            if "price" in val and val["price"] is not None:
                variation = 1 + (random.random() - 0.5) * 0.03
                snapshot[key] = {"price": round(val["price"] * variation, 2)}
        if snapshot:
            history["history"][d] = snapshot

    # Sample news items
    items = []
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
                published_at=today - timedelta(hours=random.randint(1, 23)),
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

    print(f"  News: {len(items)} sample items")
    print("Rendering...")

    date_str = today.strftime("%Y-%m-%d")
    # Compute prev/next day links (check if adjacent files exist locally)
    prev_url, next_url = None, None
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    daily_dir = Path("docs/daily")
    if (daily_dir / f"{yesterday}-morning-zh.html").exists():
        prev_url = f"{yesterday}-morning-zh.html"
    if (daily_dir / f"{tomorrow}-morning-zh.html").exists():
        next_url = f"{tomorrow}-morning-zh.html"
    latest_url = "../index.html"

    s = DailySummarizer()
    structured = s.get_structured_data(
        items, date_str, 100,
        language="zh", period="morning", score_threshold=4.0,
        market_data=market_data, market_history=history,
        market_indicators_meta=meta,
        prev_url=prev_url, next_url=next_url, latest_url=latest_url,
    )
    structured["is_demo"] = True
    html = DailyRenderer().render_html(structured)

    demo = Path("docs/daily/demo-market.html")
    demo.parent.mkdir(parents=True, exist_ok=True)
    demo.write_text(html, encoding="utf-8")
    # Also generate index.html for the "Latest" nav button
    index_html = DailyRenderer().render_index(f"daily/{date_str}-morning-zh.html")
    (Path("docs") / "index.html").write_text(index_html, encoding="utf-8")
    print("  docs/index.html (redirects to latest)")

    print(f"\nDone: {demo} ({demo.stat().st_size:,} bytes)")
    print(f"Open: file://{demo.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
