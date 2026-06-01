"""AI-based image selection for content items.

Selects informative (data, charts, benchmarks, diagrams) images from
candidate images extracted during RSS scraping. Uses a single batched
AI API call to classify all candidates at once.
"""

import json
import logging
from typing import List, Optional

from .client import AIClient
from .prompts import IMAGE_SELECTION_SYSTEM, IMAGE_SELECTION_USER
from .utils import parse_json_response
from ..models import ContentItem

logger = logging.getLogger(__name__)


class ImageSelector:
    """Selects informative images from candidate images using AI.

    Processes ContentItem.metadata["candidate_images"] and writes
    selected informational images to metadata["selected_images"].

    Follows Horizon AI module conventions: receives AIClient in the
    constructor, uses parse_json_response for robust parsing, and
    degrades gracefully on any error.
    """

    def __init__(self, ai_client: AIClient):
        """Initialize image selector.

        Args:
            ai_client: AI client instance for API calls
        """
        self.client = ai_client

    async def select_images(self, items: List[ContentItem]) -> None:
        """For high-scoring items, batch-judge candidate images via AI.

        Collects all candidate_images across all items, makes one AI API
        call for classification, then writes informational images to
        each item's metadata["selected_images"].

        Graceful degradation: on any error, leaves selected_images
        unset (absent from metadata).

        Args:
            items: Content items to process (modified in-place)
        """
        # Collect all candidate images with their parent item index
        all_candidates: List[dict] = []
        item_indices: List[int] = []

        for item_idx, item in enumerate(items):
            candidates = item.metadata.get("candidate_images", [])
            if not candidates:
                continue
            for candidate in candidates:
                all_candidates.append(candidate)
                item_indices.append(item_idx)

        if not all_candidates:
            return

        try:
            results = await self._batch_classify(all_candidates)
        except Exception:
            logger.warning("Image classification failed, degrading gracefully")
            return

        if not results:
            return

        # Map classification results back to items
        selected_by_item: dict = {}
        for result in results:
            idx = result.get("index")
            category = result.get("category", "").lower()
            if idx is None or idx < 0 or idx >= len(all_candidates):
                continue
            if category == "informational":
                item_idx = item_indices[idx]
                selected_by_item.setdefault(item_idx, []).append(
                    all_candidates[idx]
                )

        # Write selected images to item metadata
        for item_idx, images in selected_by_item.items():
            items[item_idx].metadata["selected_images"] = images

    async def _batch_classify(self, candidates: List[dict]) -> Optional[list]:
        """Classify all candidate images in a single AI API call.

        Args:
            candidates: List of candidate image dicts with url, alt,
                        before, after keys

        Returns:
            List of result dicts with index, category, confidence,
            or None if parsing/API fails
        """
        # Build a simplified representation for the AI prompt
        images_for_prompt = []
        for i, c in enumerate(candidates):
            images_for_prompt.append({
                "index": i,
                "alt": c.get("alt", ""),
                "before": c.get("before", ""),
                "after": c.get("after", ""),
            })

        # Serialise the candidate list to JSON
        images_json = json.dumps(images_for_prompt, indent=2, ensure_ascii=False)

        # Pre-escape braces in the JSON so Python str.format() does not
        # confuse them with template placeholders. format() will un-escape
        # {{ back to { and }} back to }.
        images_json_safe = images_json.replace("{", "{{").replace("}", "}}")

        user_prompt = IMAGE_SELECTION_USER.format(
            n=len(images_for_prompt),
            images_json=images_json_safe,
        )

        response = await self.client.complete(
            system=IMAGE_SELECTION_SYSTEM,
            user=user_prompt,
        )

        result = parse_json_response(response)
        if result is None:
            return None

        return result.get("results", [])
