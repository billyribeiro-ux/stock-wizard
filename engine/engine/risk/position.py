"""ATR-based trade-plan helpers: stop, targets, reward/risk, and position size."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..schemas import Side


@dataclass(frozen=True)
class TradePlan:
    entry: Decimal
    stop: Decimal
    targets: list[Decimal]
    rr: float
    size: Decimal | None = None


def _d(x: float) -> Decimal:
    return Decimal(str(round(x, 4)))


def build_plan(
    side: Side,
    entry: float,
    atr: float,
    stop_atr: float = 1.0,
    target_atrs: tuple[float, ...] = (1.5, 3.0),
    account_risk: float | None = None,
    risk_per_unit_cap: float | None = None,
) -> TradePlan:
    """Construct a symmetric ATR trade plan. ``account_risk`` (dollars) sizes the
    position so a stop-out loses ~account_risk."""
    sign = 1 if side == Side.LONG else -1
    stop = entry - sign * stop_atr * atr
    targets = [entry + sign * m * atr for m in target_atrs]
    risk = abs(entry - stop)
    reward = abs(targets[0] - entry) if targets else 0.0
    rr = (reward / risk) if risk > 0 else 0.0

    size: Decimal | None = None
    if account_risk and risk > 0:
        per_unit = risk_per_unit_cap or risk
        if per_unit > 0:
            size = _d(account_risk / per_unit)

    return TradePlan(
        entry=_d(entry),
        stop=_d(stop),
        targets=[_d(t) for t in targets],
        rr=round(rr, 2),
        size=size,
    )
