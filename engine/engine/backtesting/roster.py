"""Blend per-symbol walk-forward results into one out-of-sample edge weight per scanner.

Validating a scanner on a single symbol is noisy; the honest read is its edge *pooled*
across a basket. ``blend_forward_tests`` pools the out-of-sample trades from each symbol's
forward test, recomputes combined metrics, makes one promotion decision on that pooled
evidence, and derives the edge-weight multiplier the live signal path applies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .metrics import compute_metrics
from .walkforward import ForwardTest, _decide


@dataclass
class BlendedEdge:
    scanner_id: str
    n_symbols: int
    total_oos_trades: int
    blended_profit_factor: float
    blended_win_rate: float
    promote_fraction: float  # share of symbols that individually promoted
    promotion: str  # pooled decision: promote | keep_testing | retire
    edge_weight: float
    per_symbol: list[dict] = field(default_factory=list)


def blend_forward_tests(
    scanner_id: str, results: list[tuple[str, ForwardTest]]
) -> BlendedEdge | None:
    """Blend ``(symbol, ForwardTest)`` pairs for one scanner. Returns None if none ran."""
    from ..evidence import edge_weight_from_walkforward

    results = [(s, ft) for s, ft in results if ft is not None]
    if not results:
        return None

    pooled_trades = []
    promotes = 0
    per_symbol: list[dict] = []
    for symbol, ft in results:
        pooled_trades.extend(ft.out_of_sample.trades)
        if ft.promotion == "promote":
            promotes += 1
        per_symbol.append(
            {
                "symbol": symbol,
                "promotion": ft.promotion,
                "oos_profit_factor": ft.forward.get("profit_factor", 0.0),
                "oos_trades": ft.forward.get("total_trades", 0),
            }
        )

    combined = compute_metrics(pooled_trades, [])
    cm = combined.model_dump(mode="json")
    promotion, _ = _decide({}, cm)
    pf = float(cm.get("profit_factor", 0.0))
    edge_weight = edge_weight_from_walkforward(promotion, pf)

    return BlendedEdge(
        scanner_id=scanner_id,
        n_symbols=len(results),
        total_oos_trades=int(cm.get("total_trades", 0)),
        blended_profit_factor=round(pf, 4),
        blended_win_rate=round(float(cm.get("win_rate", 0.0)), 4),
        promote_fraction=round(promotes / len(results), 4),
        promotion=promotion,
        edge_weight=round(edge_weight, 4),
        per_symbol=per_symbol,
    )
