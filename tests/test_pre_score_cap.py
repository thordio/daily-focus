"""Tests for per-topic pre-score capping (before AI scoring).

The pre-score cap (``FilteringConfig.pre_score_max_per_topic``) limits the
number of items per topic that proceed to expensive AI scoring.  The
implementation lives in ``HorizonOrchestrator.run()`` at lines 92-108 of
``orchestrator.py``.

For unit-testing convenience, the logic is mirrored in the
``_apply_pre_score_cap`` helper below.  When the orchestrator's
implementation changes, update this helper to match.
"""

from __future__ import annotations

from collections import defaultdict

from src.models import ContentItem, FilteringConfig
from tests.conftest_helpers import make_content_item


# ---------------------------------------------------------------------------
# Helper that mirrors the orchestrator's pre-score cap logic
# ---------------------------------------------------------------------------


def _apply_pre_score_cap(
    items: list[ContentItem], cap: int
) -> list[ContentItem]:
    """Group by topic, then keep the first ``cap`` items per topic.

    Mirrors the orchestrator's implementation:

        pre_score_max = self.config.filtering.pre_score_max_per_topic
        if pre_score_max > 0:
            topic_items: dict[str, list] = defaultdict(list)
            for item in merged_items:
                topic = item.metadata.get("topic", "ai-tech")
                topic_items[topic].append(item)
            capped_items = []
            for topic, items_list in topic_items.items():
                kept = items_list[:pre_score_max]
                capped_items.extend(kept)
            merged_items = capped_items
    """
    if cap <= 0:
        return list(items)

    topic_groups: dict[str, list[ContentItem]] = defaultdict(list)
    for item in items:
        topic = item.metadata.get("topic", "ai-tech")
        topic_groups[topic].append(item)

    result: list[ContentItem] = []
    for group in topic_groups.values():
        result.extend(group[:cap])
    return result


# ---------------------------------------------------------------------------
# Config field tests
# ---------------------------------------------------------------------------


def test_pre_score_max_per_topic_default_is_50() -> None:
    """FilteringConfig has pre_score_max_per_topic with default 50."""
    cfg = FilteringConfig()
    assert cfg.pre_score_max_per_topic == 50


def test_pre_score_max_per_topic_custom_value() -> None:
    """FilteringConfig accepts custom pre_score_max_per_topic."""
    cfg = FilteringConfig.model_validate(
        {
            "ai_score_threshold": 6.0,
            "pre_score_max_per_topic": 100,
        }
    )
    assert cfg.pre_score_max_per_topic == 100


def test_pre_score_max_per_topic_round_trip() -> None:
    """pre_score_max_per_topic round-trips through serialization."""
    cfg = FilteringConfig(
        ai_score_threshold=6.0,
        pre_score_max_per_topic=100,
    )
    dumped = cfg.model_dump()
    assert dumped["pre_score_max_per_topic"] == 100
    loaded = FilteringConfig.model_validate(dumped)
    assert loaded.pre_score_max_per_topic == 100


def test_pre_score_max_per_topic_with_threshold() -> None:
    """pre_score_max_per_topic coexists with other FilteringConfig fields."""
    cfg = FilteringConfig(
        ai_score_threshold=7.5,
        time_window_hours=12,
        pre_score_max_per_topic=30,
    )
    assert cfg.ai_score_threshold == 7.5
    assert cfg.time_window_hours == 12
    assert cfg.pre_score_max_per_topic == 30


def test_pre_score_max_per_topic_typed_as_int() -> None:
    """pre_score_max_per_topic is an integer field."""
    cfg = FilteringConfig(pre_score_max_per_topic=50)
    assert isinstance(cfg.pre_score_max_per_topic, int)


# ---------------------------------------------------------------------------
# Cap behavior tests (using helper that mirrors orchestrator logic)
# ---------------------------------------------------------------------------


def _make_topic_item(item_id: str, topic: str) -> ContentItem:
    """Create a ContentItem with a specific topic in metadata."""
    return make_content_item(
        item_id=item_id,
        title=f"Item {item_id}",
        url=f"https://example.com/{item_id}",
        ai_score=None,  # pre-score — not yet analyzed
        metadata={"topic": topic},
    )


def test_pre_score_cap_within_limit_keeps_all() -> None:
    """When items per topic are under the cap, all items are kept."""
    items = [
        _make_topic_item("a1", "ai-tech"),
        _make_topic_item("a2", "ai-tech"),
        _make_topic_item("a3", "ai-tech"),
    ]
    capped = _apply_pre_score_cap(items, cap=50)
    assert len(capped) == 3


def test_pre_score_cap_exceeds_limit_trims() -> None:
    """When items per topic exceed the cap, excess items are dropped."""
    items = [_make_topic_item(f"a{i}", "ai-tech") for i in range(100)]
    capped = _apply_pre_score_cap(items, cap=50)
    assert len(capped) == 50


def test_pre_score_cap_min_actual() -> None:
    """``min(actual, cap)`` — fewer items than cap keeps all."""
    items = [_make_topic_item(f"a{i}", "ai-tech") for i in range(10)]
    capped = _apply_pre_score_cap(items, cap=50)
    assert len(capped) == 10


def test_pre_score_cap_different_topics_independent() -> None:
    """Different topics have independent caps."""
    items = []
    # 70 ai-tech items, 30 ai-markets items, 5 economy items
    for i in range(70):
        items.append(_make_topic_item(f"tech-{i}", "ai-tech"))
    for i in range(30):
        items.append(_make_topic_item(f"mkt-{i}", "ai-markets"))
    for i in range(5):
        items.append(_make_topic_item(f"econ-{i}", "economy"))

    capped = _apply_pre_score_cap(items, cap=50)

    # Count per topic
    topic_counts: dict[str, int] = {}
    for item in capped:
        t = item.metadata.get("topic", "ai-tech")
        topic_counts[t] = topic_counts.get(t, 0) + 1

    assert topic_counts["ai-tech"] == 50  # capped
    assert topic_counts["ai-markets"] == 30  # under cap
    assert topic_counts["economy"] == 5  # under cap


def test_pre_score_cap_no_items() -> None:
    """Empty list produces empty result."""
    capped = _apply_pre_score_cap([], cap=50)
    assert capped == []


def test_pre_score_cap_no_topic_defaults_ai_tech() -> None:
    """Items without topic metadata default to ai-tech for cap purposes."""
    items = [
        make_content_item(
            item_id="no-topic-1",
            metadata={"feed_name": "Test"},
        ),
        make_content_item(
            item_id="no-topic-2",
            metadata={"feed_name": "Test"},
        ),
    ]
    capped = _apply_pre_score_cap(items, cap=50)
    assert len(capped) == 2
    for item in capped:
        assert item.metadata.get("topic", "ai-tech") == "ai-tech"


def test_pre_score_cap_one_topic_over_one_under() -> None:
    """One topic over cap, another under — each handled independently."""
    items = []
    for i in range(60):
        items.append(_make_topic_item(f"tech-{i}", "ai-tech"))
    for i in range(20):
        items.append(_make_topic_item(f"mkt-{i}", "ai-markets"))

    capped = _apply_pre_score_cap(items, cap=50)
    assert len(capped) == 70  # 50 ai-tech + 20 ai-markets


def test_pre_score_cap_only_first_items_kept() -> None:
    """Items beyond the cap are dropped; first N items per topic kept."""
    items = [
        _make_topic_item("first", "ai-tech"),
        _make_topic_item("second", "ai-tech"),
        _make_topic_item("third", "ai-tech"),
    ]
    capped = _apply_pre_score_cap(items, cap=2)
    assert len(capped) == 2
    assert capped[0].id.endswith("first")
    assert capped[1].id.endswith("second")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_pre_score_cap_zero_disabled() -> None:
    """pre_score_max_per_topic=0 means the cap is disabled (all items pass).

    This matches the orchestrator's ``if pre_score_max > 0`` guard.
    """
    items = [_make_topic_item(f"a{i}", "ai-tech") for i in range(100)]
    capped = _apply_pre_score_cap(items, cap=0)
    assert len(capped) == 100


def test_pre_score_cap_negative_disabled() -> None:
    """Negative pre_score_max_per_topic means the cap is disabled."""
    items = [_make_topic_item(f"a{i}", "ai-tech") for i in range(50)]
    capped = _apply_pre_score_cap(items, cap=-1)
    assert len(capped) == 50


# ---------------------------------------------------------------------------
# Integration-style: verify default 50 cap behavior
# ---------------------------------------------------------------------------


def test_pre_score_cap_default_50_each_topic_under_limit() -> None:
    """With default cap of 50, verify no topic exceeds 50 items."""
    items = []
    for topic in ("ai-tech", "ai-markets", "economy"):
        for i in range(45):
            items.append(_make_topic_item(f"{topic}-{i}", topic))

    capped = _apply_pre_score_cap(items, cap=50)
    assert len(capped) == 135  # all 135 under the 50-per-topic cap
    topic_counts: dict[str, int] = {}
    for item in capped:
        t = item.metadata.get("topic", "ai-tech")
        topic_counts[t] = topic_counts.get(t, 0) + 1
    for count in topic_counts.values():
        assert count <= 50


def test_pre_score_cap_each_topic_exactly_at_limit() -> None:
    """When each topic has exactly `cap` items, all pass through."""
    items = []
    for topic in ("ai-tech", "ai-markets", "economy"):
        for i in range(50):
            items.append(_make_topic_item(f"{topic}-{i}", topic))

    capped = _apply_pre_score_cap(items, cap=50)
    assert len(capped) == 150  # all three topics exactly at cap


def test_pre_score_cap_mixed_preserves_other_metadata() -> None:
    """Capped items retain their original fields (not just id/topic)."""
    items = [
        _make_topic_item("keep-1", "ai-tech"),
        _make_topic_item("keep-2", "ai-tech"),
        _make_topic_item("drop-1", "ai-tech"),
    ]
    items[0].ai_summary = "Important item"
    items[0].content = "Full content here"

    capped = _apply_pre_score_cap(items, cap=2)
    assert len(capped) == 2
    assert capped[0].ai_summary == "Important item"
    assert capped[0].content == "Full content here"
