"""Self-Learning Discovery — replay past price history and self-identify WHY price
was bought and sold at every significant turning point.

Given any lookback window and timeframe (scalping = 1m/5m, intraday/day = 15m-1h,
swing = 1d+), the engine:

1. Finds every significant turn: a pivot low followed by a rally = a **BOUGHT** event;
   a pivot high followed by a decline = a **SOLD** event (minimum move filter in ATR
   units so noise is ignored).
2. At each event bar it inspects the as-of-safe feature vector and self-identifies the
   evidence reasons present at that exact moment (oversold flush, volume climax,
   dry-up, VWAP/band stretch, OBV divergence, compression, structure break...).
3. Aggregates each reason against a **baseline** (mean forward move of all turns) to get
   its *lift*, with a Welch t-stat vs the turns lacking it, then **validates** every
   reason on a held-out out-of-sample slice. A reason only ``holds_up`` if its lift is
   positive in-sample AND out-of-sample with enough samples — the platform's "prove it"
   standard, not just description.
4. Loop closure: reasons that hold up are emitted as ``suggested_rules`` — runnable
   ``custom_rule`` condition sets, so a validated discovery becomes a live, backtestable,
   alertable scanner in one click.

Reasons (features) are as-of-safe (computed from data up to the turn bar); only the
labels (which bar was a pivot, the forward move) use later bars, as a historical study
should. Results export to CSV (event log) and PDF (validated reason report).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..features.atr import atr as atr_series
from ..features.base import ohlcv_to_frame
from ..schemas import OHLCV, Timeframe
from .dataset import compute_feature_frame

_STYLE = {
    "1m": "scalping",
    "5m": "scalping",
    "15m": "intraday",
    "30m": "intraday",
    "1h": "day_trading",
    "4h": "day_trading",
    "1d": "swing",
    "1wk": "swing",
    "1mo": "position",
}


@dataclass(frozen=True)
class Reason:
    code: str
    label: str
    detail: str


@dataclass
class TurnEvent:
    ts: str
    kind: str  # "bought" | "sold"
    price: float
    forward_move_pct: float  # move to the next opposing pivot
    forward_move_atr: float
    reasons: list[Reason] = field(default_factory=list)


@dataclass
class ReasonStat:
    code: str
    label: str
    count: int
    pct_of_events: float
    avg_forward_move_pct: float
    baseline_move_pct: float = 0.0  # mean forward move across ALL turns of this kind
    lift: float = 0.0  # in-sample: avg_forward_move - baseline
    t_stat: float = 0.0  # reason group vs the rest (Welch)
    oos_count: int = 0
    oos_avg_move_pct: float = 0.0
    oos_lift: float = 0.0  # out-of-sample lift over OOS baseline
    holds_up: bool = False  # positive lift in-sample AND out-of-sample w/ enough samples


@dataclass(frozen=True)
class SuggestedRule:
    """A validated discovery reason translated into a runnable custom_rule."""

    name: str
    direction: str  # LONG | SHORT
    conditions: list[dict]  # custom_rule condition dicts
    source_reason: str
    in_sample_lift: float
    oos_lift: float


@dataclass
class DiscoveryReport:
    symbol: str
    timeframe: str
    trade_style: str
    period_start: str
    period_end: str
    n_bars: int
    n_events: int
    n_bought: int
    n_sold: int
    events: list[TurnEvent]
    buy_reasons: list[ReasonStat]
    sell_reasons: list[ReasonStat]
    baseline_buy_move: float = 0.0
    baseline_sell_move: float = 0.0
    suggested_rules: list[SuggestedRule] = field(default_factory=list)
    validated_split: float = 0.6  # fraction used for in-sample learning


# Map each discovery reason to a runnable custom_rule condition (feature/op/threshold).
_REASON_TO_CONDITION: dict[str, dict] = {
    "rsi_oversold": {"feature": "rsi14", "op": "lt", "threshold": 35},
    "rsi_overbought": {"feature": "rsi14", "op": "gt", "threshold": 65},
    "stretched_below_mean": {"feature": "dist_sma20_atr", "op": "lt", "threshold": -1.5},
    "stretched_above_mean": {"feature": "dist_sma20_atr", "op": "gt", "threshold": 1.5},
    "band_extreme_low": {"feature": "bb_pctb", "op": "lt", "threshold": 0.1},
    "band_extreme_high": {"feature": "bb_pctb", "op": "gt", "threshold": 0.9},
    "volume_climax": {"feature": "rvol", "op": "gt", "threshold": 2.0},
    "volume_dry_up": {"feature": "rvol", "op": "lt", "threshold": 0.5},
    "momentum_flush": {"feature": "ret_5", "op": "lt", "threshold": -0.01},
    "momentum_blowoff": {"feature": "ret_5", "op": "gt", "threshold": 0.01},
    "obv_divergence_bull": {"feature": "obv_slope", "op": "gt", "threshold": 0.0},
    "obv_divergence_bear": {"feature": "obv_slope", "op": "lt", "threshold": 0.0},
    "climactic_bar": {"feature": "range_atr", "op": "gt", "threshold": 1.6},
    "compression_turn": {"feature": "range_atr", "op": "lt", "threshold": 0.5},
}


def _pivots(df, k: int, min_move_atr: float, a) -> list[tuple[int, str]]:
    """Alternating significant pivots: (index, 'low'|'high')."""
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    n = len(df)
    raw: list[tuple[int, str]] = []
    for i in range(k, n - k):
        if highs[i] == highs[i - k : i + k + 1].max():
            raw.append((i, "high"))
        elif lows[i] == lows[i - k : i + k + 1].min():
            raw.append((i, "low"))
    # Enforce alternation + minimum move between consecutive pivots.
    out: list[tuple[int, str]] = []
    for idx, kind in raw:
        if not out:
            out.append((idx, kind))
            continue
        pidx, pkind = out[-1]
        if kind == pkind:  # keep the more extreme of same-kind pivots
            if (kind == "high" and highs[idx] > highs[pidx]) or (
                kind == "low" and lows[idx] < lows[pidx]
            ):
                out[-1] = (idx, kind)
            continue
        ref_a = float(a.iloc[idx]) if not np.isnan(a.iloc[idx]) else 0.0
        move = abs(
            (highs[idx] if kind == "high" else lows[idx])
            - (highs[pidx] if pkind == "high" else lows[pidx])
        )
        if ref_a > 0 and move < min_move_atr * ref_a:
            continue
        out.append((idx, kind))
    return out


def _identify_reasons(row: dict, kind: str) -> list[Reason]:
    """The self-identification battery: which evidence was present at the turn."""
    reasons: list[Reason] = []

    def add(code, label, detail):
        reasons.append(Reason(code=code, label=label, detail=detail))

    rsi = row.get("rsi14")
    if rsi is not None and not np.isnan(rsi):
        if kind == "bought" and rsi <= 32:
            add("rsi_oversold", "RSI oversold", f"RSI {rsi:.0f} — sellers exhausted")
        if kind == "sold" and rsi >= 68:
            add("rsi_overbought", "RSI overbought", f"RSI {rsi:.0f} — buyers exhausted")

    dist = row.get("dist_sma20_atr")
    if dist is not None and not np.isnan(dist):
        if kind == "bought" and dist <= -1.5:
            add(
                "stretched_below_mean",
                "Stretched below the mean",
                f"{dist:.1f} ATR under the 20-bar mean — rubber band",
            )
        if kind == "sold" and dist >= 1.5:
            add(
                "stretched_above_mean",
                "Stretched above the mean",
                f"{dist:+.1f} ATR over the 20-bar mean — rubber band",
            )

    bb = row.get("bb_pctb")
    if bb is not None and not np.isnan(bb):
        if kind == "bought" and bb <= 0.05:
            add("band_extreme_low", "Lower-band extreme", f"%B {bb:.2f} — pierced the lower band")
        if kind == "sold" and bb >= 0.95:
            add("band_extreme_high", "Upper-band extreme", f"%B {bb:.2f} — pierced the upper band")

    rvol = row.get("rvol")
    if rvol is not None and not np.isnan(rvol):
        if rvol >= 2.0:
            add(
                "volume_climax",
                "Volume climax",
                f"RVOL {rvol:.1f} — capitulation/euphoria volume at the turn",
            )
        elif rvol <= 0.5:
            add(
                "volume_dry_up",
                "Volume dry-up",
                f"RVOL {rvol:.1f} — the aggressing side ran out of fuel",
            )

    r5 = row.get("ret_5")
    if r5 is not None and not np.isnan(r5):
        if kind == "bought" and r5 <= -0.01:
            add("momentum_flush", "Momentum flush", f"{r5:+.1%} 5-bar flush into the low")
        if kind == "sold" and r5 >= 0.01:
            add("momentum_blowoff", "Momentum blow-off", f"{r5:+.1%} 5-bar thrust into the high")

    obv = row.get("obv_slope")
    if obv is not None and r5 is not None and not (np.isnan(obv) or np.isnan(r5)):
        if kind == "bought" and obv > 0 and r5 < 0:
            add(
                "obv_divergence_bull",
                "Bullish OBV divergence",
                "Price fell while cumulative volume flow rose — quiet accumulation",
            )
        if kind == "sold" and obv < 0 and r5 > 0:
            add(
                "obv_divergence_bear",
                "Bearish OBV divergence",
                "Price rose while cumulative volume flow fell — quiet distribution",
            )

    rng = row.get("range_atr")
    if rng is not None and not np.isnan(rng):
        if rng >= 1.6:
            add(
                "climactic_bar",
                "Climactic range bar",
                f"{rng:.1f}x ATR bar — forced hands at the extreme",
            )
        elif rng <= 0.5:
            add(
                "compression_turn",
                "Compression at the turn",
                f"{rng:.1f}x ATR bar — coiled before reversing",
            )

    if not reasons:
        add(
            "no_obvious_signature",
            "No obvious signature",
            "Turn happened without classic evidence — likely flow/catalyst driven",
        )
    return reasons


def discover(
    ohlcv: OHLCV,
    swing_k: int = 3,
    min_move_atr: float = 1.5,
    max_events: int = 400,
    train_frac: float = 0.6,
) -> DiscoveryReport | None:
    """Run self-learning discovery over the given history window."""
    df = ohlcv_to_frame(ohlcv)
    if len(df) < 60:
        return None
    feats = compute_feature_frame(df)
    a = atr_series(df, 14)
    closes = df["close"].to_numpy(dtype=float)

    pivots = _pivots(df, swing_k, min_move_atr, a)
    if len(pivots) < 2:
        return None

    events: list[TurnEvent] = []
    for j in range(len(pivots) - 1):
        idx, kind = pivots[j]
        nidx, _ = pivots[j + 1]
        price = float(df["low"].iloc[idx] if kind == "low" else df["high"].iloc[idx])
        nprice = float(df["high"].iloc[nidx] if kind == "low" else df["low"].iloc[nidx])
        move = (nprice - price) / price if kind == "low" else (price - nprice) / price
        ref_a = float(a.iloc[idx]) if not np.isnan(a.iloc[idx]) else 0.0
        move_atr = abs(nprice - price) / ref_a if ref_a > 0 else 0.0
        ekind = "bought" if kind == "low" else "sold"
        row = feats.iloc[idx].to_dict()
        row["close"] = closes[idx]
        events.append(
            TurnEvent(
                ts=df.index[idx].isoformat(),
                kind=ekind,
                price=round(price, 4),
                forward_move_pct=round(move, 5),
                forward_move_atr=round(move_atr, 2),
                reasons=_identify_reasons(row, ekind),
            )
        )
    events = events[-max_events:]

    # Time-ordered learn/validate split — discovery must prove a reason out-of-sample,
    # not just describe the past (the platform's precision standard).
    split = int(len(events) * train_frac)
    train_events = events[:split]
    valid_events = events[split:]

    def _moves(evs, kind):
        return [e.forward_move_pct for e in evs if e.kind == kind]

    def _aggregate(kind: str) -> tuple[list[ReasonStat], float]:
        train_sub = [e for e in train_events if e.kind == kind]
        valid_sub = [e for e in valid_events if e.kind == kind]
        all_sub = [e for e in events if e.kind == kind]
        if not all_sub:
            return [], 0.0
        baseline = float(np.mean(_moves(all_sub, kind))) if all_sub else 0.0
        base_tr = float(np.mean(_moves(train_sub, kind))) if train_sub else baseline
        base_va = float(np.mean(_moves(valid_sub, kind))) if valid_sub else baseline

        # group moves by reason code, separately for train and validation
        def grouped(evs):
            g: dict[str, list] = {}
            for e in evs:
                for r in e.reasons:
                    g.setdefault(r.code, [r.label, []])[1].append(e.forward_move_pct)
            return g

        tr = grouped(train_sub)
        va = grouped(valid_sub)
        tr_moves_all = _moves(train_sub, kind)

        stats: list[ReasonStat] = []
        for code, (label, moves) in tr.items():
            mean_r = float(np.mean(moves))
            lift = mean_r - base_tr
            # Welch t: this reason's turns vs the turns WITHOUT it (per-event, not by value).
            rest = [
                e.forward_move_pct for e in train_sub if code not in {r.code for r in e.reasons}
            ] or tr_moves_all
            t_stat = _welch_t(moves, rest)
            oos_label_moves = va.get(code, [label, []])[1]
            oos_n = len(oos_label_moves)
            oos_mean = float(np.mean(oos_label_moves)) if oos_n else 0.0
            oos_lift = (oos_mean - base_va) if oos_n else 0.0
            holds = lift > 0 and oos_lift > 0 and oos_n >= max(3, len(valid_sub) // 20)
            stats.append(
                ReasonStat(
                    code=code,
                    label=label,
                    count=len(moves),
                    pct_of_events=round(len(moves) / max(len(train_sub), 1), 4),
                    avg_forward_move_pct=round(mean_r, 5),
                    baseline_move_pct=round(base_tr, 5),
                    lift=round(lift, 5),
                    t_stat=round(t_stat, 3),
                    oos_count=oos_n,
                    oos_avg_move_pct=round(oos_mean, 5),
                    oos_lift=round(oos_lift, 5),
                    holds_up=holds,
                )
            )
        # Rank: validated edge first (holds_up), then in-sample lift x sqrt(count).
        stats.sort(key=lambda s: (s.holds_up, s.lift * (s.count**0.5)), reverse=True)
        return stats, baseline

    buy_reasons, base_buy = _aggregate("bought")
    sell_reasons, base_sell = _aggregate("sold")

    # Loop closure: turn validated reasons into runnable custom_rule candidates.
    suggested: list[SuggestedRule] = []
    for direction, reasons in (("LONG", buy_reasons), ("SHORT", sell_reasons)):
        for s in reasons:
            if s.holds_up and s.code in _REASON_TO_CONDITION:
                suggested.append(
                    SuggestedRule(
                        name=f"{s.label} ({direction})",
                        direction=direction,
                        conditions=[_REASON_TO_CONDITION[s.code]],
                        source_reason=s.code,
                        in_sample_lift=s.lift,
                        oos_lift=s.oos_lift,
                    )
                )

    bought = [e for e in events if e.kind == "bought"]
    sold = [e for e in events if e.kind == "sold"]
    tf = ohlcv.timeframe.value if isinstance(ohlcv.timeframe, Timeframe) else str(ohlcv.timeframe)
    return DiscoveryReport(
        symbol=ohlcv.symbol,
        timeframe=tf,
        trade_style=_STYLE.get(tf, "swing"),
        period_start=df.index[0].isoformat(),
        period_end=df.index[-1].isoformat(),
        n_bars=len(df),
        n_events=len(events),
        n_bought=len(bought),
        n_sold=len(sold),
        events=events,
        buy_reasons=buy_reasons,
        sell_reasons=sell_reasons,
        baseline_buy_move=round(base_buy, 5),
        baseline_sell_move=round(base_sell, 5),
        suggested_rules=suggested,
        validated_split=train_frac,
    )


def _welch_t(group: list[float], rest: list[float]) -> float:
    """Welch's t-statistic comparing a reason group's forward moves to the rest."""
    if len(group) < 2 or len(rest) < 2:
        return 0.0
    g, r = np.asarray(group, dtype=float), np.asarray(rest, dtype=float)
    vg, vr = g.var(ddof=1), r.var(ddof=1)
    denom = np.sqrt(vg / len(g) + vr / len(r))
    if denom <= 1e-12:
        return 0.0
    return float((g.mean() - r.mean()) / denom)
