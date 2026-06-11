"""RSS feed scraper implementation."""

import asyncio
import calendar
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
import httpx
import feedparser
from bs4 import BeautifulSoup

from .base import BaseScraper
from ..models import ContentItem, SourceType, RSSSourceConfig

logger = logging.getLogger(__name__)


class RSSScraper(BaseScraper):
    """Scraper for RSS/Atom feeds."""

    def __init__(self, sources: List[RSSSourceConfig], http_client: httpx.AsyncClient):
        """Initialize RSS scraper.

        Args:
            sources: List of RSS feed configurations
            http_client: Shared async HTTP client
        """
        super().__init__({"sources": sources}, http_client)

    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch RSS feed items concurrently.

        Args:
            since: Only fetch items published after this time

        Returns:
            List[ContentItem]: Fetched content items
        """
        sources = [s for s in self.config["sources"] if s.enabled]
        if not sources:
            return []

        image_cache = self._load_image_cache()
        results = await asyncio.gather(
            *(self._fetch_feed(source, since, image_cache=image_cache) for source in sources),
            return_exceptions=True,
        )
        items = []
        for source, result in zip(sources, results):
            if isinstance(result, Exception):
                logger.warning("Error fetching RSS feed %s: %s", source.name, result)
            elif isinstance(result, list):
                items.extend(result)
        self._save_image_cache(image_cache)
        return items

    async def _fetch_feed(
        self, source: RSSSourceConfig, since: datetime, image_cache: Dict[str, int] = None
    ) -> List[ContentItem]:
        """Fetch items from a single RSS feed.

        Args:
            source: RSS feed configuration
            since: Only fetch items after this time
            image_cache: Optional shared image URL cache. If not provided,
                         a local cache is loaded and saved independently.

        Returns:
            List[ContentItem]: Feed content items
        """
        items = []
        own_cache = image_cache is None
        if own_cache:
            image_cache = self._load_image_cache()
        feed_url_str = str(source.url)

        try:
            # Expand environment variables in URL (e.g. ${LWN_TOKEN})
            feed_url = re.sub(
                r"\$\{(\w+)\}",
                lambda m: os.environ.get(m.group(1), m.group(0)).strip(),
                str(source.url),
            )

            # Fetch feed content
            response = await self.client.get(
                feed_url,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
            )
            response.raise_for_status()

            # Parse feed
            feed = feedparser.parse(response.text)

            for entry in feed.entries:
                # Parse published date
                published_at = self._parse_date(entry)
                if not published_at or published_at < since:
                    continue

                # Generate unique ID from feed URL and entry ID
                feed_id = str(source.url).split("//")[1].replace("/", "_")
                entry_id = entry.get("id", entry.get("link", ""))
                entry_hash = hashlib.sha256(str(entry_id).encode("utf-8")).hexdigest()[
                    :16
                ]

                # Extract content
                content = self._extract_content(entry)

                # Extract candidate images from content HTML
                candidate_images = self._extract_candidate_images(entry, image_cache, feed_url_str)

                item = ContentItem(
                    id=self._generate_id("rss", feed_id, entry_hash),
                    source_type=SourceType.RSS,
                    title=entry.get("title", "Untitled"),
                    url=entry.get("link", str(source.url)),
                    content=content,
                    author=entry.get("author", source.name),
                    published_at=published_at,
                    metadata={
                        "feed_name": source.name,
                        "category": source.category,
                        "topic": source.topic,
                        "tags": [tag.term for tag in entry.get("tags", [])],
                        "candidate_images": candidate_images,
                    },
                )
                items.append(item)

        except httpx.HTTPError as e:
            logger.warning("Error fetching RSS feed %s: %s", source.name, e)
        except Exception as e:
            logger.warning("Error parsing RSS feed %s: %s", source.name, e)

        # Cap items per source to max_items — keep most recent first
        if len(items) > source.max_items:
            items = items[:source.max_items]

        if own_cache:
            self._save_image_cache(image_cache)
        return items

    def _parse_date(self, entry: dict) -> datetime:
        """Parse publication date from feed entry.

        Args:
            entry: Feed entry data

        Returns:
            datetime: Parsed publication date or None
        """
        # Try different date fields
        for field in ["published", "updated", "created"]:
            if field in entry:
                try:
                    # Try parsing structured time first
                    if f"{field}_parsed" in entry and entry[f"{field}_parsed"]:
                        return datetime.fromtimestamp(
                            calendar.timegm(entry[f"{field}_parsed"]), tz=timezone.utc
                        )
                    # Fallback to string parsing
                    date_str = entry[field]
                    return parsedate_to_datetime(date_str)
                except Exception:
                    continue

        return None

    def _extract_content(self, entry: dict) -> str:
        """Extract text content from feed entry.

        Args:
            entry: Feed entry data

        Returns:
            str: Extracted text content
        """
        # Try different content fields
        if "summary" in entry:
            return entry.summary
        if "description" in entry:
            return entry.description
        if "content" in entry and entry.content:
            # content is usually a list
            return entry.content[0].get("value", "")

        return ""

    def _load_image_cache(self) -> Dict[str, int]:
        """Load image URL frequency cache from data/image_cache.json.

        Returns:
            dict mapping image URL -> number of times seen
        """
        cache_path = Path(__file__).resolve().parents[2] / "data" / "image_cache.json"
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_image_cache(self, cache: Dict[str, int]) -> None:
        """Persist image URL frequency cache to data/image_cache.json."""
        cache_path = Path(__file__).resolve().parents[2] / "data" / "image_cache.json"
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        except OSError:
            logger.debug("Failed to write image cache", exc_info=True)

    def _extract_candidate_images(self, entry: dict, cache: Dict[str, int], feed_url: str) -> List[dict]:
        """Extract candidate images from feed entry content HTML.

        Parses the content HTML with BeautifulSoup, finds all img tags,
        applies rule-based filtering (logo/avatar/icon/headshot/button),
        checks URL dedup cache, resolves relative URLs, and returns at
        most 5 candidates per entry. Updates the cache in-place for
        extracted URLs.

        Args:
            entry: Feed entry data
            cache: Image URL frequency cache (mutated in-place)
            feed_url: Base URL for resolving relative image URLs

        Returns:
            List of dicts with keys: url, alt, before, after
        """
        # Get HTML content (same field resolution as _extract_content)
        html = ""
        if "summary" in entry:
            html = entry.summary
        elif "description" in entry:
            html = entry.description
        elif "content" in entry and entry.content:
            html = entry.content[0].get("value", "")

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        img_tags = soup.find_all("img")
        if not img_tags:
            return []

        # Patterns that indicate decorative/non-informational images
        skip_patterns = ["logo", "avatar", "icon", "headshot", "button"]

        candidates: List[dict] = []
        for img in img_tags:
            raw_src = img.get("src", "")
            if not raw_src:
                continue

            # Resolve relative URLs against the feed URL
            src = urljoin(feed_url, raw_src)

            # Rule-based pre-filter: skip decorative URLs
            src_lower = src.lower()
            if any(p in src_lower for p in skip_patterns):
                continue

            # URL dedup: skip URLs seen more than 3 times
            if cache.get(src, 0) > 3:
                continue

            # Track URL frequency in dedup cache
            cache[src] = cache.get(src, 0) + 1

            alt = img.get("alt", "") or ""

            # Extract surrounding context by locating the img tag
            # in the original HTML via its src attribute. Search for
            # the original (possibly relative) URL first, since the
            # HTML contains the raw attribute value from the feed.
            src_idx = html.find(raw_src)
            if src_idx == -1:
                src_idx = html.find(src)  # fallback: try resolved URL
            before_text = ""
            after_text = ""
            if src_idx != -1:
                # Estimate img tag boundaries in the original HTML
                tag_start = html.rfind("<img", 0, src_idx)
                if tag_start == -1:
                    tag_start = src_idx
                tag_end = html.find(">", tag_start) + 1
                if tag_end <= 0:
                    tag_end = tag_start + len(src)

                before_html = html[max(0, tag_start - 200) : tag_start]
                after_html = html[tag_end : tag_end + 200]
                before_text = (
                    BeautifulSoup(before_html, "html.parser")
                    .get_text(separator=" ", strip=True)[-100:]
                )
                after_text = (
                    BeautifulSoup(after_html, "html.parser")
                    .get_text(separator=" ", strip=True)[:100]
                )

            candidates.append({
                "url": src,
                "alt": alt,
                "before": before_text,
                "after": after_text,
            })

            if len(candidates) >= 5:
                break

        return candidates
