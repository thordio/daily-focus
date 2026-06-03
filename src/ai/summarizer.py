"""Daily summary generation — pure programmatic rendering."""

import re
from collections import defaultdict
from typing import List, Dict

from ..models import ContentItem


_CJK = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_ASCII = r"[A-Za-z0-9]"
_CJK_RE = re.compile(_CJK)


def _has_cjk(text: str) -> bool:
    """Check if text contains any CJK (Chinese) characters."""
    return bool(_CJK_RE.search(text))


def _pangu(text: str) -> str:
    """Insert a space between CJK and ASCII letters/digits (Pangu spacing)."""
    text = re.sub(rf"({_CJK})({_ASCII})", r"\1 \2", text)
    text = re.sub(rf"({_ASCII})({_CJK})", r"\1 \2", text)
    return text


LABELS = {
    "en": {
        "header": "Horizon Daily",
        "source": "Source",
        "background": "Background",
        "discussion": "Discussion",
        "references": "References",
        "tags": "Tags",
        "selected_items": "From {total} items, {selected} important content pieces were selected",
        "empty_analyzed": "Analyzed {total} items, but none met the importance threshold.",
        "empty_body": (
            "No significant developments today. This might indicate:\n"
            "- A quiet day in your tracked sources\n"
            "- The AI score threshold is too high\n"
            "- Your information sources need expansion\n\n"
            "Consider:\n"
            "1. Lowering the `ai_score_threshold` in config.json\n"
            "2. Adding more diverse information sources\n"
            "3. Checking if the AI model is working correctly\n"
        ),
    },
    "zh": {
        "header": "Horizon 每日速递",
        "source": "来源",
        "background": "背景",
        "discussion": "社区讨论",
        "references": "参考链接",
        "tags": "标签",
        "selected_items": "从 {total} 条内容中筛选出 {selected} 条重要资讯。",
        "empty_analyzed": "已分析 {total} 条内容，但没有达到重要性阈值的条目。",
        "empty_body": (
            "今日暂无重要动态，可能原因：\n"
            "- 今天关注的信息源较平静\n"
            "- AI 评分阈值设置过高\n"
            "- 信息源种类有待扩充\n\n"
            "建议：\n"
            "1. 在 config.json 中降低 `ai_score_threshold`\n"
            "2. 添加更多多样化的信息源\n"
            "3. 检查 AI 模型是否正常工作\n"
        ),
    },
}


class DailySummarizer:
    """Generates daily Markdown summaries from pre-analyzed content items."""

    def __init__(self):
        pass

    async def generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary in Markdown format.

        Items are rendered in score-descending order (already sorted by orchestrator).

        Args:
            items: High-scoring content items (already enriched)
            date: Date string (YYYY-MM-DD)
            total_fetched: Total number of items fetched before filtering
            language: Output language, either "en" or "zh"

        Returns:
            str: Markdown formatted summary
        """
        labels = LABELS.get(language, LABELS["en"])

        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        header = (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['selected_items'].format(total=total_fetched, selected=len(items))}\n\n"
            "---\n\n"
        )

        # TOC
        toc_entries = []
        for i, item in enumerate(items):
            _t = item.metadata.get(f"title_{language}") or item.title
            t = str(_t).replace("[", "(").replace("]", ")")
            if language == "zh":
                t = _pangu(t)
            score = item.ai_score or "?"
            toc_entries.append(f"{i + 1}. [{t}](#item-{i + 1}) \u2b50\ufe0f {score}/10")
        toc = "\n".join(toc_entries) + "\n\n---\n\n"

        parts = [self._format_item(item, labels, language, i + 1) for i, item in enumerate(items)]

        return header + toc + "".join(parts)

    def generate_webhook_overview(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate a compact overview for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        if language == "zh":
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> 从 {total_fetched} 条内容中筛选出 {len(items)} 条重要资讯。\n\n"
                "下面会按新闻逐条发送详情，你可以只看感兴趣的标题。\n\n"
            )
        else:
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> Selected {len(items)} important items from {total_fetched} fetched items.\n\n"
                "Details will be sent item by item so you can read only the topics you care about.\n\n"
            )

        entries = []
        for i, item in enumerate(items, start=1):
            title = str(item.metadata.get(f"title_{language}") or item.title).replace("[", "(").replace("]", ")")
            if language == "zh":
                title = _pangu(title)
            score = item.ai_score or "?"
            entries.append(f"{i}. [{title}]({item.url}) \u2b50\ufe0f {score}/10")

        return header + "\n".join(entries)

    def generate_webhook_item(
        self,
        item: ContentItem,
        language: str,
        index: int,
        total: int,
    ) -> str:
        """Generate one item message for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        prefix = f"第 {index}/{total} 条\n\n" if language == "zh" else f"Item {index}/{total}\n\n"
        return prefix + self._format_item(item, labels, language, index).rstrip("-\n ")

    def _format_item(self, item: ContentItem, labels: dict, language: str, index: int) -> str:
        """Format a single ContentItem into Markdown."""
        _title = item.metadata.get(f"title_{language}") or item.title
        title = str(_title).replace("[", "(").replace("]", ")")
        url = str(item.url)
        score = item.ai_score or "?"
        meta = item.metadata

        summary = (
            meta.get(f"detailed_summary_{language}")
            or meta.get("detailed_summary")
            or item.ai_summary
            or ""
        )
        background = meta.get(f"background_{language}") or meta.get("background") or ""
        discussion = (
            meta.get(f"community_discussion_{language}")
            or meta.get("community_discussion")
            or ""
        )

        if language == "zh":
            title = _pangu(title)
            summary = _pangu(summary)
            background = _pangu(background)
            discussion = _pangu(discussion)

        # Source line with parts joined by " · ", link appended at end
        source_type = item.source_type.value
        source_parts = [source_type]
        if meta.get("subreddit"):
            source_parts.append(f"r/{meta['subreddit']}")
        if meta.get("feed_name"):
            source_parts.append(meta["feed_name"])
        else:
            source_parts.append(item.author or "unknown")
        if item.published_at:
            if language == "zh":
                source_parts.append(
                    f"{item.published_at.month}月{item.published_at.day}日 "
                    f"{item.published_at:%H:%M}"
                )
            else:
                day = item.published_at.strftime("%d").lstrip("0")
                source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
        source_line = " \u00b7 ".join(source_parts)  # ·

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            discussion_url = str(discussion_url)
            if discussion_url != url:
                source_line += f' · [{labels["discussion"]}]({discussion_url})'

        lines = [
            f'<a id="item-{index}"></a>',
            f"## [{title}]({url}) \u2b50\ufe0f {score}/10",  # ⭐️
            "",
            summary,
            "",
            source_line,
        ]

        if background:
            lines.append("")
            lines.append(f"**{labels['background']}**: {background}")

        sources = meta.get("sources") or []
        if sources:
            items_html = "".join(f'<li><a href="{s["url"]}">{s["title"]}</a></li>\n' for s in sources)
            lines += [
                "",
                f'<details><summary>{labels["references"]}</summary>\n<ul>\n{items_html}\n</ul>\n</details>',
            ]

        if discussion:
            lines.append("")
            lines.append(f"**{labels['discussion']}**: {discussion}")

        if item.ai_tags:
            tags_str = ", ".join([f"`#{t}`" for t in item.ai_tags])
            lines.append("")
            lines.append(f"**{labels['tags']}**: {tags_str}")

        lines.append("")
        lines.append("---")

        return "\n".join(lines) + "\n\n"

    TAB_DEFS = {
        "ai-tech": {"label": "AI 技术", "label_en": "AI Tech"},
        "ai-markets": {"label": "AI 市场", "label_en": "AI Markets"},
        "economy": {"label": "经济动向", "label_en": "Economy"},
    }

    @staticmethod
    def _item_to_dict(item: ContentItem, index: int, language: str) -> Dict:
        """Convert a single ContentItem into the dict format used by structured data and tabs."""
        meta = item.metadata

        # source_label: most descriptive display name
        source_label = (
            meta.get("feed_name")
            or meta.get("subreddit", "")
            or item.author
            or item.source_type.value
        )
        if meta.get("subreddit"):
            source_label = f"r/{meta['subreddit']}"

        # whats_new: try design-doc field first, then enricher output, then AI summary
        whats_new = (
            meta.get(f"whats_new_{language}")
            or meta.get("whats_new")
            or meta.get(f"detailed_summary_{language}")
            or meta.get("detailed_summary")
            or item.ai_summary
            or ""
        )

        # why_it_matters: try design-doc field first, then AI reason, then enricher output
        why_it_matters = (
            meta.get(f"why_it_matters_{language}")
            or meta.get("why_it_matters")
            or meta.get(f"detailed_summary_{language}")
            or item.ai_reason
            or ""
        )

        # key_details: try language-suffixed field first, then generic, then detailed_summary
        key_details = (
            meta.get(f"key_details_{language}")
            or meta.get("key_details")
            or ""
        )

        # background
        background = (
            meta.get(f"background_{language}")
            or meta.get("background")
            or ""
        )

        # community_discussion (separate from why_it_matters)
        community_discussion = (
            meta.get(f"community_discussion_{language}")
            or meta.get("community_discussion")
            or ""
        )

        tags = item.ai_tags or []

        # images from selected_images
        images = meta.get("selected_images") or []

        # references from sources (also support "references" for manual/demo data)
        references = meta.get("sources") or meta.get("references") or []

        # title_en: try metadata first, then item.title
        title_en = str(meta.get("title_en") or item.title)

        # Detect language mismatch: when language is "zh", flag if displayed text
        # fields are non-empty but contain no CJK characters (AI returned English
        # despite being asked for Chinese).
        language_mismatch = False
        if language == "zh":
            _texts = [whats_new, why_it_matters, background, community_discussion]
            _non_empty = [t for t in _texts if t.strip()]
            if _non_empty and not any(_has_cjk(t) for t in _non_empty):
                language_mismatch = True

        return {
            "index": index + 1,
            "title": str(meta.get(f"title_{language}") or item.title),
            "title_en": title_en,
            "url": str(item.url),
            "score": item.ai_score or 0.0,
            "source_label": source_label,
            "source_type": item.source_type.value,
            "published_at": item.published_at.isoformat() if item.published_at else "",
            "whats_new": whats_new,
            "why_it_matters": why_it_matters,
            "key_details": key_details,
            "ai_reason": item.ai_reason or "",
            "background": background,
            "community_discussion": community_discussion,
            "tags": tags,
            "images": images,
            "references": references,
            "language_mismatch": language_mismatch,
        }

    def get_structured_data(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
        period: str = "morning",
        score_threshold: float = 7.0,
    ) -> Dict:
        """Return structured dict for Jinja2 HTML rendering.

        Items are grouped by ``metadata.get("topic", "ai-tech")`` into
        named tabs. The returned dict includes both a flat ``items`` list
        (backward-compat) and a ``tabs`` dict for tabbed rendering.

        Produces a dict matching the schema defined in ``daily-focus-design.md``
        Section 5, Work Area C, Step 1.

        Args:
            items: High-scoring content items (already enriched).
            date: Date string (YYYY-MM-DD).
            total_fetched: Total items fetched before filtering.
            language: Output language, either "en" or "zh".
            period: "morning" for 早报 or "evening" for 晚报.
            score_threshold: AI score threshold used for filtering.

        Returns:
            A dict ready to pass to ``DailyRenderer.render_html()``.
        """
        # Next update string
        if period == "morning":
            next_update = "今晚 20:00" if language == "zh" else "Tonight 20:00"
        else:
            next_update = "明早 08:00" if language == "zh" else "Tomorrow 08:00"

        # Build the flat item-data list (backward-compat) and grouped tabs
        flat_items = []
        grouped: Dict[str, list] = defaultdict(list)
        for i, item in enumerate(items):
            item_dict = self._item_to_dict(item, i, language)
            flat_items.append(item_dict)
            topic = item.metadata.get("topic", "ai-tech")
            grouped[topic].append(item_dict)

        tabs = {}
        for tab_key, tab_def in self.TAB_DEFS.items():
            tabs[tab_key] = {
                "label": tab_def["label"],
                "label_en": tab_def["label_en"],
                "items": grouped.get(tab_key, []),
            }

        # Alternate-language URL for the language switcher link
        other_lang = "en" if language == "zh" else "zh"
        alternate_url = f"{date}-{period}-{other_lang}.html"

        return {
            "date": date,
            "period": period,
            "language": language,
            "total_fetched": total_fetched,
            "selected_count": len(items),
            "score_threshold": score_threshold,
            "next_update": next_update,
            "items": flat_items,  # backward-compat flat list
            "tabs": tabs,
            "active_tab": "ai-tech",
            "alternate_url": alternate_url,
        }

    def _generate_empty_summary(self, date: str, total_fetched: int, labels: dict) -> str:
        """Generate summary when no high-scoring items were found."""
        return (
            f"# {labels['header']} - {date}\n\n"
            f"> {labels['empty_analyzed'].format(total=total_fetched)}\n\n"
            + labels["empty_body"]
        )
