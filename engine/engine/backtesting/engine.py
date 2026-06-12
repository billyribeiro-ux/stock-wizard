"""Event-driven backtester.

Replays bars chronologically with no lookahead: at each bar a FeatureSnapshot is built
from data known *up to that bar*, the scanner runs, and a single-position-at-a-time
trade model executes the resulting signal with an ATR stop/target plan and realistic
costs (commission + slippage). Produces a BacktestResult with trades, equity curve, and
full metrics. Works with any scanner that needs only OHLCV (+ optional HTF).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from ..features import FeatureFactory
from ..risk import build_plan
from ..scanners import build_scanner
from ..schemas import (
    OHLCV,
    BacktestResult,
    EquityPoint,
    MarketBar,
    Side,
    TradeRecord,
)
from .metrics import compute_metrics


@dataclass
class BacktestConfig:
    starting_equity: float = 10_000.0
    risk_per_trade: float = 0.01  # fraction of equity risked per trade
    commission: float = 0.0  # $ per trade per side
    slippage_bps: float = 1.0  # basis points of entry/exit price
    stop_atr: float = 1.0
    target_atrs: tuple[float, ...] = (1.5, 3.0)
    warmup: int = 60
    min_score: float = 0.4
    time_stop_bars: int = 60
    allow_short: bool = True


@dataclass
class _OpenPosition:
    side: Side
    entry_ts: datetime
    entry: float
    stop: float
    target: float
    size: float
    bars_held: int = 0
    mfe: float = 0.0
    mae: float = 0.0


@dataclass
class _State:
    equity: float
    trades: list[TradeRecord] = field(default_factory=list)
    curve: list[EquityPoint] = field(default_factory=list)
    bars_in_trade: int = 0


class BacktestEngine:
    def __init__(self, config: BacktestConfig | None = None):
        self.cfg = config or BacktestConfig()
        self.factory = FeatureFactory()

    def run(
        self,
        scanner_id: str,
        ohlcv: OHLCV,
        params: dict | None = None,
        htf_ohlcv: OHLCV | None = None,
    ) -> BacktestResult:
        from ..scanners.base import ScanContext

        cfg = self.cfg
        bars = ohlcv.bars
        state = _State(equity=cfg.starting_equity)
        pos: _OpenPosition | None = None
        scanner = build_scanner(scanner_id, params)
        slip = cfg.slippage_bps / 10_000.0

        for i in range(cfg.warmup, len(bars)):
            bar = bars[i]
            window = OHLCV(
                symbol=ohlcv.symbol,
                timeframe=ohlcv.timeframe,
                asset_class=ohlcv.asset_class,
                source=ohlcv.source,
                bars=bars[: i + 1],
            )
            htf_window = _htf_window(htf_ohlcv, bar.ts)

            # --- manage an open position against this bar ---
            if pos is not None:
                state.bars_in_trade += 1
                pos.bars_held += 1
                exit_px, reason = self._check_exit(pos, bar, cfg)
                self._update_excursion(pos, bar)
                if exit_px is not None:
                    self._close(state, pos, bar.ts, exit_px, reason, slip, cfg)
                    pos = None

            # --- look for a new entry (flat only) ---
            if pos is None:
                snap = self.factory.build_snapshot(window)
                ctx = ScanContext(
                    symbol=ohlcv.symbol,
                    timeframe=ohlcv.timeframe,
                    snapshot=snap,
                    ohlcv=window,
                    htf_ohlcv=htf_window,
                    as_of=bar.ts,
                )
                res = scanner.run(ctx)
                if (
                    res.triggered
                    and res.score >= cfg.min_score
                    and res.direction in (Side.LONG, Side.SHORT)
                    and (cfg.allow_short or res.direction == Side.LONG)
                ):
                    atr = (res.feature_refs or {}).get("atr.14") or snap.get("atr.14")
                    if atr and atr > 0:
                        pos = self._open(state, res.direction, bar, float(atr), slip, cfg)

            state.curve.append(EquityPoint(ts=bar.ts, equity=Decimal(str(round(state.equity, 2)))))

        # close any residual position at the last bar
        if pos is not None and bars:
            self._close(state, pos, bars[-1].ts, float(bars[-1].close), "end_of_data", slip, cfg)

        years = _years(bars)
        metrics = compute_metrics(
            state.trades,
            state.curve,
            state.bars_in_trade,
            max(len(bars) - cfg.warmup, 1),
            years=years,
            starting_equity=cfg.starting_equity,
        )
        return BacktestResult(
            scanner_id=scanner_id,
            params=params or {},
            universe=[ohlcv.symbol],
            period_start=bars[0].ts.date() if bars else datetime.now().date(),
            period_end=bars[-1].ts.date() if bars else datetime.now().date(),
            trades=state.trades,
            equity_curve=state.curve,
            metrics=metrics,
        )

    # ------------------------------------------------------------------ #
    def _open(self, state, side, bar, atr, slip, cfg) -> _OpenPosition:
        raw = float(bar.close)
        entry = raw * (1 + slip) if side == Side.LONG else raw * (1 - slip)
        plan = build_plan(side, entry, atr, stop_atr=cfg.stop_atr, target_atrs=cfg.target_atrs)
        risk_per_unit = abs(entry - float(plan.stop))
        size = (state.equity * cfg.risk_per_trade / risk_per_unit) if risk_per_unit > 0 else 0.0
        return _OpenPosition(
            side=side,
            entry_ts=bar.ts,
            entry=entry,
            stop=float(plan.stop),
            target=float(plan.targets[0]),
            size=max(size, 0.0),
        )

    def _check_exit(self, pos, bar: MarketBar, cfg) -> tuple[float | None, str]:
        hi, lo = float(bar.high), float(bar.low)
        if pos.side == Side.LONG:
            if lo <= pos.stop:
                return pos.stop, "stop"
            if hi >= pos.target:
                return pos.target, "target"
        else:
            if hi >= pos.stop:
                return pos.stop, "stop"
            if lo <= pos.target:
                return pos.target, "target"
        if pos.bars_held >= cfg.time_stop_bars:
            return float(bar.close), "time_stop"
        return None, ""

    def _update_excursion(self, pos, bar: MarketBar) -> None:
        hi, lo = float(bar.high), float(bar.low)
        if pos.side == Side.LONG:
            pos.mfe = max(pos.mfe, hi - pos.entry)
            pos.mae = min(pos.mae, lo - pos.entry)
        else:
            pos.mfe = max(pos.mfe, pos.entry - lo)
            pos.mae = min(pos.mae, pos.entry - hi)

    def _close(self, state, pos, ts, exit_px, reason, slip, cfg) -> None:
        fill = exit_px * (1 - slip) if pos.side == Side.LONG else exit_px * (1 + slip)
        sign = 1 if pos.side == Side.LONG else -1
        pnl = (fill - pos.entry) * sign * pos.size - 2 * cfg.commission
        state.equity += pnl
        ret = ((fill - pos.entry) * sign / pos.entry) if pos.entry else 0.0
        state.trades.append(
            TradeRecord(
                symbol="",
                side=pos.side,
                entry_ts=pos.entry_ts,
                entry_price=Decimal(str(round(pos.entry, 4))),
                exit_ts=ts,
                exit_price=Decimal(str(round(fill, 4))),
                pnl=Decimal(str(round(pnl, 4))),
                return_pct=round(ret, 6),
                mfe=round(pos.mfe, 4),
                mae=round(pos.mae, 4),
                hold_seconds=int((ts - pos.entry_ts).total_seconds()),
                exit_reason=reason,
            )
        )


def _htf_window(htf: OHLCV | None, ts: datetime) -> OHLCV | None:
    if htf is None:
        return None
    sub = [b for b in htf.bars if b.ts <= ts]
    if not sub:
        return None
    return OHLCV(symbol=htf.symbol, timeframe=htf.timeframe, source=htf.source, bars=sub)


def _years(bars: list[MarketBar]) -> float:
    if len(bars) < 2:
        return 0.0
    span = (bars[-1].ts - bars[0].ts).total_seconds()
    return span / (365.25 * 24 * 3600)
