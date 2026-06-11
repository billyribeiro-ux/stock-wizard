"""Evaluate whether a signal's invalidation condition has been hit at a new price."""

from __future__ import annotations

from ..schemas import InvalidationRule


def is_invalidated(rule: InvalidationRule, price: float, prev_price: float | None = None) -> bool:
    """Check a price-based invalidation rule against the latest (and prior) price."""
    if rule.level is None or rule.comparator is None:
        return False
    if rule.comparator == "gt":
        return price > rule.level
    if rule.comparator == "lt":
        return price < rule.level
    if rule.comparator == "crosses":
        if prev_price is None:
            return False
        return (prev_price - rule.level) * (price - rule.level) < 0
    return False
