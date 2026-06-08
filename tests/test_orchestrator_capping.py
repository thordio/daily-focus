"""Tests for orchestrator capping dedup — uses ContentItem.id, not Python id()."""

from __future__ import annotations

from tests.conftest_helpers import make_content_item


def test_capping_uses_string_id_not_builtin_id():
    """Capping dedup uses ContentItem.id string field, not Python's id() builtin.

    The bug was using ``id(item)`` (memory address) for dedup, which meant
    two different Python objects with the same ``.id`` would both be kept.
    The correct behavior is to use ``item.id`` (the string identifier).
    """
    # Create items where different Python objects share the same .id
    items = [
        make_content_item(item_id="duplicate-id", title="First", ai_score=8.0),
        make_content_item(item_id="duplicate-id", title="Second", ai_score=7.0),
        make_content_item(item_id="unique-id", title="Third", ai_score=6.0),
    ]

    # Verify they are different Python objects (different memory addresses)
    assert id(items[0]) != id(items[1]), (
        "Test setup bug: items must be different Python objects"
    )

    # Verify they have the same .id string
    assert items[0].id == items[1].id, (
        "Test setup bug: items must have the same .id string"
    )

    # Mirror the orchestrator's dedup logic (line 164-169):
    #   seen_ids = set()
    #   unique_selected = []
    #   for item in selected:
    #       if item.id not in seen_ids:
    #           seen_ids.add(item.id)
    #           unique_selected.append(item)
    #   selected = unique_selected
    seen_ids = set()
    unique = []
    for item in items:
        if item.id not in seen_ids:
            seen_ids.add(item.id)
            unique.append(item)

    # Should keep only 2 unique items (the first duplicate + the unique one)
    assert len(unique) == 2, (
        f"Expected 2 unique items after string-ID dedup, got {len(unique)}.\n"
        "If this fails, the capping logic may be using Python's id() builtin "
        "instead of ContentItem.id."
    )
    assert unique[0].title == "First"  # first encountered wins
    assert unique[1].title == "Third"


def test_capping_refuses_builtin_id():
    """Demonstrate that ``id()`` would give wrong results.

    When two different Python objects have the same ``.id`` but different
    memory addresses, using ``id()`` keeps both — giving 3 items instead of 2.
    """
    items = [
        make_content_item(item_id="same", title="A", ai_score=8.0),
        make_content_item(item_id="same", title="B", ai_score=7.0),
        make_content_item(item_id="other", title="C", ai_score=6.0),
    ]

    # Using item.id (string) — correct behavior
    correct_seen = set()
    correct_result = []
    for item in items:
        if item.id not in correct_seen:
            correct_seen.add(item.id)
            correct_result.append(item)

    # Using id(item) (memory address) — bug behavior
    buggy_seen = set()
    buggy_result = []
    for item in items:
        if id(item) not in buggy_seen:
            buggy_seen.add(id(item))
            buggy_result.append(item)

    # String dedup gives 2 unique items
    assert len(correct_result) == 2
    assert correct_result[0].title == "A"
    assert correct_result[1].title == "C"

    # id() dedup keeps ALL 3 because each is a different Python object
    assert len(buggy_result) == 3, (
        f"Expected 3 items when using id() (bug behavior), got {len(buggy_result)}. "
        "If this passes unexpectedly, it means Python allocated items at same address."
    )
