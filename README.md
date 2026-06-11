<div align="center">

# Daily Focus

**AI-powered bilingual daily news digest — AI Tech, AI Markets, Global Economy**

[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue?style=flat-square)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-8B5CF6?style=flat-square&logo=git&logoColor=white)](https://github.com/astral-sh/uv)

</div>

A personalized fork of [Horizon](https://github.com/Thysrael/Horizon) (MIT License). Daily Focus fetches, scores, enriches, and renders a curated HTML briefing daily — no noise, no filler, every claim traceable to a source.

## Key Features

- **Three Topic Tabs**: AI Technology (AI 技术), AI Markets (AI 市场), Economy (经济动向)
- **Per-topic Caps**: AI tech/markets 6-10 articles, economy 5-7 articles
- **Bilingual Output**: Chinese (zh) and English (en) editions
- **Single Daily Edition**: Generated daily via GitHub Actions cron (UTC 04:00)
- **Anti-Hallucination**: Every claim grounded in source URLs and web search; "No reliable information" fallback when uncertain
- **Pydantic v2 Models**: All data flows through validated `ContentItem` models; config validated at startup
- **Pipeline**: Fetch (RSS, GitHub, Hacker News, Reddit, Telegram, Twitter, OpenBB) → AI Score → Semantic Dedup → Cap → Web Search Enrich → AI Summarize → Render HTML
- **Deployment**: GitHub Actions cron → GitHub Pages (public repo = free unlimited Actions minutes)

## Tech Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.14 |
| Package Manager | `uv` |
| AI Provider | DeepSeek V4-Pro (OpenAI-compatible API) |
| Config | Pydantic v2 `model_validate()` |
| CI/CD | GitHub Actions → GitHub Pages |

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USER/daily-focus.git
cd daily-focus

# Install dependencies
uv sync

# Set your API key
export DEEPSEEK_API_KEY=your_key_here

# Run the pipeline
uv run horizon

# Open the result
open docs/daily/$(date +%Y-%m-%d)-zh.html
```

## Config Files

- `data/config.json` — single daily edition (24h window, threshold 4.0, concurrency 20)

All configs are validated at startup via Pydantic `Config.model_validate()`.

## GitHub Actions Setup

1. Add `DEEPSEEK_API_KEY` as a repository secret (Settings → Secrets and variables → Actions).
2. Ensure the repo is **public** (GitHub provides free unlimited Actions minutes for public repos).
3. Workflow is at `.github/workflows/daily-focus.yml`.
4. Deployment uses [`peaceiris/actions-gh-pages@v4`](https://github.com/peaceiris/actions-gh-pages) to publish to GitHub Pages.

## Pipeline

```
Config → Fetch → AI Score → Dedup → Per-topic Cap → Web Search Enrich → AI Summarize → Render HTML
```

1. **Fetch** — Pull content from RSS, Hacker News, Reddit, Telegram, Twitter, GitHub, OpenBB, OSSInsight
2. **Score** — AI rates each item 0-10 on relevance to the three topics
3. **Dedup** — Semantic deduplication merges the same story across sources
4. **Cap** — Enforce per-topic article limits (6-10 tech/markets, 5-7 economy)
5. **Enrich** — Web search for background context, grounded in source URLs
6. **Summarize** — AI generates `whats_new`, `why_it_matters`, `background` for each item
7. **Render** — Output bilingual HTML with score badges, topic tabs, reference links

## Development

```bash
# Run tests
uv run pytest tests/ -v
```

## License

[MIT](LICENSE)

Daily Focus is based on [Horizon](https://github.com/Thysrael/Horizon) (MIT License), a Python full-stack news pipeline by Thysrael.
