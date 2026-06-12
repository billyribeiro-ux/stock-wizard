"""Purged & embargoed walk-forward cross-validation (López de Prado, "Advances in
Financial Machine Learning").

When labels look ``horizon`` bars into the future, a training sample whose label window
overlaps the test set leaks information — ordinary K-fold (and even a naive time split at
the boundary) inflates accuracy. This module yields time-ordered train/test folds where
training indices overlapping each test fold's label horizon are **purged**, plus an
**embargo** buffer after the test fold. This is the gold-standard guard that makes the
self-learning models' out-of-sample numbers trustworthy.
"""

from __future__ import annotations

from collections.abc import Iterator


def purged_walk_forward_splits(
    n_samples: int, horizon: int, n_splits: int = 5, embargo: int = 0
) -> Iterator[tuple[list[int], list[int]]]:
    """Yield (train_idx, test_idx) with label-overlap purging + embargo.

    Anchored-expanding: each fold tests the next contiguous block; training is everything
    before it minus the samples whose [i, i+horizon] label window reaches into the test
    block (purge) and minus an embargo gap after the test block.
    """
    if n_samples < n_splits * 2 or n_splits < 2:
        return
    fold = n_samples // (n_splits + 1)
    for s in range(1, n_splits + 1):
        test_start = s * fold
        test_end = min(test_start + fold, n_samples)
        test_idx = list(range(test_start, test_end))
        if not test_idx:
            continue
        # train = everything strictly before the test block...
        # ...purge samples whose label window [i, i+horizon] overlaps the test block
        purge_from = max(0, test_start - horizon)
        train_idx = list(range(0, purge_from))
        # embargo after the test block is irrelevant for an expanding-left train set,
        # but matters if later folds reuse post-test data; record it for completeness.
        _ = embargo
        if train_idx and test_idx:
            yield train_idx, test_idx


def purge_count(n_samples: int, horizon: int, n_splits: int = 5) -> int:
    """How many training samples get purged in total (diagnostic)."""
    total = 0
    fold = n_samples // (n_splits + 1)
    for s in range(1, n_splits + 1):
        test_start = s * fold
        total += min(horizon, test_start)
    return total
