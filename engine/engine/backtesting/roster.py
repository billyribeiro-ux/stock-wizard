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

# Below this many pooled out-of-sample trades we can't distinguish edge from luck, so we
# stay neutral (keep_testing / weight 1.0) rather than promote or retire on noise — a
# scanner that "wins" 6 of 6 OOS trades is not a validated edge.
MIN_OOS_TRADES = 30


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
    # Per-regime edge weight (trend/range) from the OOS regime breakdown — lets a scanner
    # that's globally net-flat still be traded in the regime where it has proven edge.
    regime_edges: dict[str, float] = field(default_factory=dict)


def _regime_edges(results: list[tuple[str, ForwardTest]]) -> dict[str, float]:
    """Pool the OOS regime breakdown across symbols into a per-regime edge weight.

    Each symbol's forward test exposes ``out_of_sample.regime_breakdown`` (per-regime
    metrics). We pool trades + trade-weighted PF per regime, then map to an edge weight with
    the same trade-count floor + verdict logic used globally."""
    from ..evidence import edge_weight_from_walkforward

    pooled: dict[str, list] = {}  # regime -> [trades, pnl, win*trades, [pf...]]
    for _sym, ft in results:
        for regime, m in (ft.out_of_sample.regime_breakdown or {}).items():
            agg = pooled.setdefault(regime, [0, 0.0, 0.0, []])
            agg[0] += m.total_trades
            agg[1] += float(m.total_pnl)
            agg[2] += m.win_rate * m.total_trades
            if m.total_trades:
                agg[3].append(m.profit_factor)
    out: dict[str, float] = {}
    for regime, (trades, pnl, _w, pfs) in pooled.items():
        pf = sum(pfs) / len(pfs) if pfs else 0.0
        if trades < MIN_OOS_TRADES:
            promotion = "keep_testing"
        elif pf >= 1.3 and pnl > 0:
            promotion = "promote"
        elif pf < 1.0:
            promotion = "retire"
        else:
            promotion = "keep_testing"
        out[regime] = round(edge_weight_from_walkforward(promotion, pf), 4)
    return out


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
    total_trades = int(cm.get("total_trades", 0))
    pf = float(cm.get("profit_factor", 0.0))
    # Too few pooled OOS trades -> stay neutral (can't tell edge from luck).
    if total_trades < MIN_OOS_TRADES:
        promotion = "keep_testing"
    else:
        promotion, _ = _decide({}, cm)
    edge_weight = edge_weight_from_walkforward(promotion, pf)

    return BlendedEdge(
        scanner_id=scanner_id,
        n_symbols=len(results),
        total_oos_trades=total_trades,
        blended_profit_factor=round(pf, 4),
        blended_win_rate=round(float(cm.get("win_rate", 0.0)), 4),
        promote_fraction=round(promotes / len(results), 4),
        promotion=promotion,
        edge_weight=round(edge_weight, 4),
        per_symbol=per_symbol,
        regime_edges=_regime_edges(results),
    )
