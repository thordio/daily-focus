"""Content enrichment using AI (second-pass analysis).

For items that pass the score threshold, this module:
1. Searches the web for relevant context (via DuckDuckGo)
2. Feeds search results + item content to AI to generate grounded background knowledge
"""

import asyncio
import json
import re
import sys
import os
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from ddgs import DDGS

from .client import AIClient
from .prompts import (
    CONTENT_ENRICHMENT_SYSTEM, CONTENT_ENRICHMENT_USER,
)
from .utils import parse_json_response
from ..models import ContentItem


class ContentEnricher:
    """Enriches high-scoring content items with background knowledge."""

    # Items at or above this score get web search + full background enrichment.
    # Items below it skip web search (saving ~9s + API cost) and get enrichment
    # from article content alone.
    _MIN_SCORE_FOR_WEB_SEARCH = 7.0

    def __init__(self, ai_client: AIClient):
        self.client = ai_client

    def _get_concurrency(self) -> int:
        """Return the configured enrichment concurrency, clamped to 1 or above."""
        config = getattr(self.client, "config", None)
        concurrency = getattr(config, "enrichment_concurrency", 1)
        return max(concurrency, 1)

    async def enrich_batch(self, items: List[ContentItem]) -> None:
        """Enrich items in-place with background knowledge.

        Args:
            items: Content items to enrich (modified in-place)
        """
        concurrency = self._get_concurrency()
        semaphore = asyncio.Semaphore(concurrency)

        async def _process(item: ContentItem, progress_task) -> None:
            async with semaphore:
                try:
                    await self._enrich_item(item)
                except Exception as e:
                    print(f"Error enriching item {item.id}: {e}")
            progress.advance(progress_task)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("Enriching", total=len(items))
            coros = [
                _process(item, task) for item in items
            ]
            await asyncio.gather(*coros)

    async def _web_search(self, query: str, max_results: int = 3) -> list:
        """Search the web for context via DuckDuckGo.

        Returns:
            List of dicts with keys: title, url, body
        """
        try:
            # Suppress primp "Impersonate ... does not exist" stderr warning
            stderr = sys.stderr
            sys.stderr = open(os.devnull, "w")
            try:
                ddgs = DDGS()
                results = await asyncio.to_thread(ddgs.text, query, max_results=max_results)
            finally:
                sys.stderr.close()
                sys.stderr = stderr
        except Exception:
            return []

        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "body": r.get("body", "")}
            for r in (results or [])
        ]

    @staticmethod
    def _parse_json_response(response: str) -> Optional[dict]:
        """Try multiple strategies to extract a JSON object from an AI response.

        Returns the parsed dict, or None if all strategies fail.
        """
        return parse_json_response(response)

    @staticmethod
    def _build_enrichment_schema(languages: List[str]) -> str:
        """Build JSON schema for enrichment prompt based on configured languages.

        Only includes fields for languages that are configured, reducing output
        tokens when a single language suffices.

        Args:
            languages: List of language codes (e.g. ["en"], ["zh"], ["en", "zh"])

        Returns:
            str: JSON schema for the enrichment prompt
        """
        fields = ["title", "whats_new", "why_it_matters", "key_details", "background"]
        lines = ["{"]
        for lang in languages:
            for field in fields:
                if field == "title":
                    desc = "<short headline in English, ≤15 words>" if lang == "en" else "<用中文写一个简短标题，不超过15个词>"
                elif field == "whats_new":
                    desc = "<3-4 sentences with specific details>" if lang == "en" else "<用中文写3-4句话，包含具体细节和数据>"
                elif field == "why_it_matters":
                    desc = "<2-3 sentences connecting to broader trends>" if lang == "en" else "<用中文写2-3句话，联系更广泛的趋势和影响>"
                elif field == "key_details":
                    desc = "<2-3 sentences with technical specifics>" if lang == "en" else "<用中文写2-3句话，包含技术细节>"
                elif field == "background":
                    desc = "<2-4 sentences in English, or empty string>" if lang == "en" else "<用中文写2-4句话，或空字符串>"
                lines.append(f'  "{field}_{lang}": "{desc}",')
        lines.append('  "sources": ["<url from search results>", "..."]')
        lines.append("}")
        return "\n".join(lines)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10)
    )
    async def _enrich_item(self, item: ContentItem) -> None:
        """Enrich a single item with background knowledge.

        For items below ``_MIN_SCORE_FOR_WEB_SEARCH`` (7.0), the web search is
        skipped entirely — enrichment is generated from article content alone.
        This saves ~9s of web search time for borderline-interesting items.

        For items at or above the threshold:
        1. Search the web using the item title and tags (parallelized, no LLM call)
        2. Ask AI to generate background based on article content + search results

        Args:
            item: Content item to enrich (modified in-place via metadata)
        """
        # Extract content text and comments separately
        content_text = ""
        comments_text = ""
        if item.content:
            if "--- Top Comments ---" in item.content:
                main, comments_part = item.content.split("--- Top Comments ---", 1)
                content_text = main.strip()[:4000]
                comments_text = comments_part.strip()[:2000]
            else:
                content_text = item.content[:4000]

        # Decide whether this item warrants the cost of web search
        score = item.ai_score or 0.0
        needs_web_search = score >= self._MIN_SCORE_FOR_WEB_SEARCH

        # Web search: use item title + tags as queries (no separate LLM call needed)
        all_results = []
        web_context = ""
        available_urls = {}

        if needs_web_search:
            queries = [q for q in [item.title, ", ".join(item.ai_tags)] if q]
            if queries:
                search_results = await asyncio.gather(
                    *(self._web_search(query) for query in queries),
                    return_exceptions=True,
                )
                web_sections = []
                for query, results in zip(queries, search_results):
                    if isinstance(results, Exception):
                        continue
                    all_results.extend(results)
                    if results:
                        lines = [f"- [{r['title']}]({r['url']}): {r['body']}" for r in results]
                        web_sections.append(f"**{query}:**\n" + "\n".join(lines))
                web_context = "\n\n".join(web_sections) if web_sections else ""
                available_urls = {r["url"]: r["title"] for r in all_results if r.get("url")}

        # Determine which languages to generate
        config = getattr(self.client, "config", None)
        languages = getattr(config, "languages", ["en"])

        # Build the JSON schema dynamically based on configured languages
        json_schema = self._build_enrichment_schema(languages)

        # Step 3: AI generates enrichment grounded in article content (and web search if available)
        user_prompt = CONTENT_ENRICHMENT_USER.format(
            title=item.title,
            url=str(item.url),
            summary=item.ai_summary or item.title,
            score=score,
            reason=item.ai_reason or "",
            tags=", ".join(item.ai_tags) if item.ai_tags else "",
            content=content_text,
            comments_section=f"\n**Community Comments:**\n{comments_text}" if comments_text else "",
            web_context=web_context or "No web search results available.",
            json_schema=json_schema,
        )

        response = await self.client.complete(
            system=CONTENT_ENRICHMENT_SYSTEM,
            user=user_prompt,
        )

        # Parse JSON response with robust fallback
        result = self._parse_json_response(response)
        if result is None:
            # Gracefully degrade: skip enrichment instead of raising
            # (raising would trigger retries that won't help with a parse error)
            print(f"Warning: could not parse enrichment response for {item.id}, skipping enrichment")
            return

        # Store structured fields individually per language
        for lang in languages:
            if result.get(f"title_{lang}"):
                val = result[f"title_{lang}"]
                item.metadata[f"title_{lang}"] = val.get("text") or str(val) if isinstance(val, dict) else str(val)

            # Store EACH field separately so summarizer can read them independently
            parts = []
            for field in ("whats_new", "why_it_matters", "key_details"):
                val = result.get(f"{field}_{lang}")
                if val is not None:
                    text = val.get("text") or str(val) if isinstance(val, dict) else str(val)
                    text = text.strip()
                    if text:
                        item.metadata[f"{field}_{lang}"] = text
                        parts.append(text)

            # Also build detailed_summary_{lang} for backward compat (Markdown path)
            if parts:
                item.metadata[f"detailed_summary_{lang}"] = " ".join(parts)

            if result.get(f"background_{lang}"):
                val = result[f"background_{lang}"]
                item.metadata[f"background_{lang}"] = val.get("text") or str(val) if isinstance(val, dict) else str(val)

        # Store citation sources — only URLs that actually came from our search results
        if result.get("sources") and available_urls:
            valid = [
                {"url": u, "title": available_urls[u]}
                for u in result["sources"]
                if u in available_urls
            ]
            if valid:
                item.metadata["sources"] = valid

        # Backward-compatible fallback fields (English as default)
        item.metadata["detailed_summary"] = item.metadata.get("detailed_summary_en", "")
        item.metadata["background"] = item.metadata.get("background_en", "")
