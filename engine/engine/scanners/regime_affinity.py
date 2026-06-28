"""Scanner regime affinities — which market regime each scanner has *validated* edge in.

Derived from the regime-segmented backtests (see ``docs/BACKTESTS.md``): the engine tags
every trade with its entry regime (trend vs range via the Kaufman Efficiency Ratio) and
breaks down performance per regime. Scanners with a clear regime dependence are gated here
so the live signal path can demote them when the current regime is unfavourable.

Scanners absent from ``SCANNER_REGIMES`` are treated as regime-agnostic (no gate) — e.g.
``breakout_quality`` and ``volume_profile_poc``, which carried positive edge in both regimes.
"""

from __future__ import annotations

from ..features.regime import RANGE, TREND, TREND_ER

# scanner_id -> the set of regimes where it has demonstrated out-of-sample / segmented edge.
SCANNER_REGIMES: dict[str, set[str]] = {
    # mtf_structure: net negative in range, clearly positive in trend (BACKTESTS.md).
    "mtf_structure": {TREND},
}


def regime_kind_from_er(er: float | None) -> str | None:
    """Map an efficiency ratio to a coarse trend/range kind (None when unknown)."""
    if er is None:
        return None
    return TREND if er >= TREND_ER else RANGE


def is_regime_aligned(scanner_id: str, er: float | None) -> bool:
    """True when the scanner is regime-agnostic, the regime is unknown, or the current
    regime is one the scanner has validated edge in. False only when we *know* the regime
    is unfavourable for a regime-specific scanner."""
    favorable = SCANNER_REGIMES.get(scanner_id)
    if favorable is None:
        return True  # agnostic — never gated
    kind = regime_kind_from_er(er)
    if kind is None:
        return True  # regime unknown — don't gate on missing data
    return kind in favorable
