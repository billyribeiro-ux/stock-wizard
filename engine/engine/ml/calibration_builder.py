"""Collect (score, outcome) pairs by replaying a scanner over history, then fit a
calibrator. Outcome = did the trade's direction make a favorable move over the horizon.
"""

from __future__ import annotations

from ..features import FeatureFactory
from ..schemas import OHLCV, Side
from .calibration import ScoreCalibrator, fit_calibrator


def build_scanner_calibrator(
    scanner_id: str,
    ohlcv: OHLCV,
    params: dict | None = None,
    horizon: int = 10,
    warmup: int = 60,
    step: int = 1,
) -> ScoreCalibrator:
    """Replay the scanner bar-by-bar; pair each triggered score with its forward outcome."""
    # Lazy import: scanners import from ml, so import here to avoid a cycle.
    from ..scanners import build_scanner
    from ..scanners.base import ScanContext

    bars = ohlcv.bars
    if len(bars) < warmup + horizon + 5:
        return ScoreCalibrator()
    closes = [float(b.close) for b in bars]
    factory = FeatureFactory()
    scanner = build_scanner(scanner_id, params)

    scores: list[float] = []
    outcomes: list[int] = []
    for i in range(warmup, len(bars) - horizon, step):
        window = OHLCV(
            symbol=ohlcv.symbol,
            timeframe=ohlcv.timeframe,
            asset_class=ohlcv.asset_class,
            source=ohlcv.source,
            bars=bars[: i + 1],
        )
        snap = factory.build_snapshot(window)
        ctx = ScanContext(
            symbol=ohlcv.symbol,
            timeframe=ohlcv.timeframe,
            snapshot=snap,
            ohlcv=window,
            as_of=bars[i].ts,
        )
        res = scanner.run(ctx)
        if not res.triggered or res.direction not in (Side.LONG, Side.SHORT):
            continue
        fwd = (closes[i + horizon] - closes[i]) / closes[i]
        win = 1 if (fwd > 0) == (res.direction == Side.LONG) else 0
        scores.append(res.score)
        outcomes.append(win)

    return fit_calibrator(scores, outcomes)


__all__ = ["build_scanner_calibrator"]
