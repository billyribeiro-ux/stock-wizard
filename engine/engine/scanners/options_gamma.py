"""Options & gamma scanners operating on the live OptionChain.

These complement the SPX 0DTE Gamma Command engine with focused single-factor reads:
GEX regime, hedge walls, squeezes, expected move, pin/magnet, max pain, skew, charm/
vanna pressure, and unusual options flow.
"""

from __future__ import annotations

from ..features import gex as gex_mod
from ..features import options_metrics as om
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, OptionRight, ScannerResult, Side
from ._common import ev, flat, levels, make_result
from .base import ScanContext, Scanner


def _profile(ctx):
    chain = ctx.chain
    if chain is None or not chain.expiries:
        return None, None, None
    expiry = chain.expiries[0]
    t = om.years_to_expiry(chain.as_of, expiry)
    return chain, expiry, gex_mod.compute_gex_profile(chain, t, expiry)


class GammaExposureScanner(Scanner):
    scanner_id = "gamma_exposure"
    name = "Gamma Exposure / GX"
    description = "Estimated dealer GEX by strike, total exposure, and the volatility regime."
    category = "options_gamma"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        _chain, _, gp = _profile(ctx)
        if gp is None:
            return flat(self, ctx, "insufficient_data", "No option chain / GEX profile.", "options")
        positive = gp.regime == "positive"
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=None,
            score=min(1.0, abs(gp.total_gex) / 1e10 + 0.4),
            classification="positive_gamma" if positive else "negative_gamma",
            why=(
                "Positive dealer gamma — hedging dampens volatility (mean-reverting tape)."
                if positive
                else "Negative dealer gamma — hedging amplifies moves (trending/volatile tape)."
            ),
            why_now=f"Total GEX = {gp.total_gex:,.0f}; flip at {gp.flip}.",
            invalidation=InvalidationRule(
                description="Spot crosses the gamma flip",
                kind="options",
                level=gp.flip,
                comparator="crosses",
            ),
            evidence_for=[
                ev(
                    EK.OPTIONS,
                    "total_gex",
                    round(gp.total_gex, 0),
                    0.6,
                    Side.NEUTRAL,
                    self.scanner_id,
                )
            ],
            level_map=levels(
                spot=gp.spot, flip=gp.flip, call_wall=gp.call_wall, put_wall=gp.put_wall
            ),
        )


class GammaWallScanner(Scanner):
    scanner_id = "gamma_wall"
    name = "Gamma Hedge Wall"
    description = "Reaction at the nearest high-gamma strike (resistance above / support below)."
    category = "options_gamma"
    default_params = {"near_atr": 0.6}
    params_schema = {
        "type": "object",
        "properties": {"near_atr": {"type": "number", "default": 0.6}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        _chain, _, gp = _profile(ctx)
        atr = ctx.snapshot.get("atr.14") or 0.0
        if gp is None or atr <= 0:
            return flat(self, ctx, "insufficient_data", "No GEX profile / ATR.", "options")
        spot = gp.spot
        near = self.params["near_atr"] * atr
        if gp.call_wall is not None and 0 <= gp.call_wall - spot <= near:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=0.55,
                classification="call_wall_resistance",
                why=f"Price is testing the call (gamma) wall at {gp.call_wall:.2f}.",
                why_now="In positive gamma, dealers sell into strength near the wall.",
                invalidation=InvalidationRule(
                    description=f"Acceptance above {gp.call_wall:.2f}",
                    kind="price",
                    level=gp.call_wall,
                    comparator="gt",
                ),
                evidence_for=[
                    ev(EK.OPTIONS, "call_wall", gp.call_wall, 0.6, Side.SHORT, self.scanner_id)
                ],
                level_map=levels(spot=spot, call_wall=gp.call_wall),
            )
        if gp.put_wall is not None and 0 <= spot - gp.put_wall <= near:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=0.55,
                classification="put_wall_support",
                why=f"Price is testing the put (gamma) wall at {gp.put_wall:.2f}.",
                why_now="In positive gamma, dealers buy into weakness near the wall.",
                invalidation=InvalidationRule(
                    description=f"Breakdown below {gp.put_wall:.2f}",
                    kind="price",
                    level=gp.put_wall,
                    comparator="lt",
                ),
                evidence_for=[
                    ev(EK.OPTIONS, "put_wall", gp.put_wall, 0.6, Side.LONG, self.scanner_id)
                ],
                level_map=levels(spot=spot, put_wall=gp.put_wall),
            )
        return flat(self, ctx, "no_wall_test", "Price not near a gamma wall.", "options")


class GammaSqueezeScanner(Scanner):
    scanner_id = "gamma_squeeze"
    name = "Gamma Squeeze"
    description = "Spot breaching a wall in negative gamma where hedging may accelerate the move."
    category = "options_gamma"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        _chain, _, gp = _profile(ctx)
        if gp is None:
            return flat(self, ctx, "insufficient_data", "No GEX profile.", "options")
        if gp.regime != "negative":
            return flat(self, ctx, "no_squeeze", "Positive gamma — squeeze fuel absent.", "options")
        spot = gp.spot
        rvol = ctx.snapshot.get("rvol.20") or 1.0
        if gp.call_wall is not None and spot > gp.call_wall:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=0.5 + 0.25 * (rvol >= 1.3),
                classification="gamma_squeeze_up",
                why="Spot broke the call wall in negative gamma; hedging may fuel a squeeze higher.",
                why_now=f"Spot {spot:.2f} > call wall {gp.call_wall:.2f}.",
                invalidation=InvalidationRule(
                    description=f"Back below {gp.call_wall:.2f}",
                    kind="price",
                    level=gp.call_wall,
                    comparator="lt",
                ),
                evidence_for=[
                    ev(
                        EK.OPTIONS,
                        "breach_call_wall",
                        gp.call_wall,
                        0.6,
                        Side.LONG,
                        self.scanner_id,
                    ),
                    ev(EK.VOLUME, "rvol", round(rvol, 2), 0.25, Side.LONG, self.scanner_id),
                ],
                level_map=levels(spot=spot, call_wall=gp.call_wall),
            )
        if gp.put_wall is not None and spot < gp.put_wall:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=0.5 + 0.25 * (rvol >= 1.3),
                classification="gamma_squeeze_down",
                why="Spot broke the put wall in negative gamma; hedging may fuel a slide lower.",
                why_now=f"Spot {spot:.2f} < put wall {gp.put_wall:.2f}.",
                invalidation=InvalidationRule(
                    description=f"Back above {gp.put_wall:.2f}",
                    kind="price",
                    level=gp.put_wall,
                    comparator="gt",
                ),
                evidence_for=[
                    ev(EK.OPTIONS, "breach_put_wall", gp.put_wall, 0.6, Side.SHORT, self.scanner_id)
                ],
                level_map=levels(spot=spot, put_wall=gp.put_wall),
            )
        return flat(self, ctx, "no_squeeze", "No wall breach in negative gamma.", "options")


class ExpectedMoveScanner(Scanner):
    scanner_id = "expected_move"
    name = "Expected Move & IV Premium"
    description = "Compares the day's move to the options-implied expected move."
    category = "options_gamma"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        chain, expiry, _ = _profile(ctx)
        if chain is None:
            return flat(self, ctx, "insufficient_data", "No option chain.", "options")
        t = om.years_to_expiry(chain.as_of, expiry)
        em = om.expected_move(chain, t, expiry)
        if em is None or em.straddle <= 0:
            return flat(self, ctx, "insufficient_data", "Expected move unavailable.", "options")
        spot = float(chain.spot)
        prev_close = ctx.snapshot.get("vp.poc") or spot  # proxy reference if no prior close
        move = abs(spot - prev_close)
        exceeded = move > em.straddle
        direction = Side.SHORT if spot > prev_close else Side.LONG
        score = min(1.0, move / em.straddle) if em.straddle else 0.0
        return make_result(
            self,
            ctx,
            triggered=exceeded,
            direction=direction if exceeded else None,
            score=score,
            classification="em_exceeded" if exceeded else "em_inside",
            why=f"Expected move ≈ {em.straddle:.2f} (ATM straddle); actual move {move:.2f}.",
            why_now=(
                "Move exceeded the implied expected move — mean-reversion edge."
                if exceeded
                else "Move is within the implied expected move."
            ),
            invalidation=InvalidationRule(description="Move keeps extending past EM", kind="price"),
            evidence_for=[
                ev(
                    EK.OPTIONS,
                    "expected_move",
                    round(em.straddle, 2),
                    0.5,
                    direction if exceeded else Side.NEUTRAL,
                    self.scanner_id,
                )
            ],
            level_map=levels(spot=spot, em_straddle=em.straddle, atm_strike=em.atm_strike),
        )


class PinMagnetScanner(Scanner):
    scanner_id = "pin_magnet"
    name = "Pin Risk & Magnet"
    description = "Large-OI strike that may pin price into expiry (chop warning in positive gamma)."
    category = "options_gamma"
    default_params = {"near_atr": 0.5}
    params_schema = {
        "type": "object",
        "properties": {"near_atr": {"type": "number", "default": 0.5}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        chain, expiry, gp = _profile(ctx)
        atr = ctx.snapshot.get("atr.14") or 0.0
        if chain is None or atr <= 0:
            return flat(self, ctx, "insufficient_data", "No chain / ATR.", "options")
        clusters = om.oi_clusters(chain, expiry, top=1)
        if not clusters:
            return flat(self, ctx, "insufficient_data", "No OI clusters.", "options")
        magnet, oi = clusters[0]
        spot = float(chain.spot)
        positive = gp is not None and gp.regime == "positive"
        if abs(spot - magnet) <= self.params["near_atr"] * atr and positive:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=None,
                score=0.5,
                classification="pin_chop_warning",
                why=f"Heavy OI at {magnet:.2f} ({oi:,}) may pin price in positive gamma.",
                why_now="Directional trades are lower-quality near a pin in positive gamma.",
                invalidation=InvalidationRule(
                    description=f"Price leaves the {magnet:.2f} pin zone", kind="price"
                ),
                evidence_for=[
                    ev(EK.OPTIONS, "oi_magnet", magnet, 0.5, Side.NEUTRAL, self.scanner_id)
                ],
                level_map=levels(spot=spot, magnet=magnet),
            )
        return flat(self, ctx, "no_pin", "Not in a pin zone.", "options")


class MaxPainScanner(Scanner):
    scanner_id = "max_pain_oi"
    name = "Max Pain & OI Cluster"
    description = "Max-pain strike as one input (a drift bias, not a prophecy)."
    category = "options_gamma"
    default_params = {"near_atr": 0.75}
    params_schema = {
        "type": "object",
        "properties": {"near_atr": {"type": "number", "default": 0.75}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        chain, expiry, _ = _profile(ctx)
        atr = ctx.snapshot.get("atr.14") or 0.0
        if chain is None or atr <= 0:
            return flat(self, ctx, "insufficient_data", "No chain / ATR.", "options")
        mp = om.max_pain(chain, expiry)
        if mp is None:
            return flat(self, ctx, "insufficient_data", "Max pain unavailable.", "options")
        spot = float(chain.spot)
        dist = (mp - spot) / atr
        if abs(dist) >= self.params["near_atr"]:
            direction = Side.LONG if dist > 0 else Side.SHORT
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=direction,
                score=min(0.6, abs(dist) / 4),
                classification="max_pain_drift",
                why=f"Max-pain at {mp:.2f} sits {dist:+.1f} ATR from spot — a gentle drift bias.",
                why_now="Into expiry, price often gravitates toward max pain when flows are quiet.",
                invalidation=InvalidationRule(
                    description="Strong trend overrides the pin", kind="price"
                ),
                evidence_for=[ev(EK.OPTIONS, "max_pain", mp, 0.4, direction, self.scanner_id)],
                level_map=levels(spot=spot, max_pain=mp),
            )
        return flat(self, ctx, "near_max_pain", "Spot already near max pain.", "options")


class SkewScanner(Scanner):
    scanner_id = "skew_term"
    name = "Skew & Term Structure"
    description = "OTM put-vs-call IV skew as a risk-appetite gauge."
    category = "options_gamma"
    default_params = {"skew_threshold": 0.03}
    params_schema = {
        "type": "object",
        "properties": {"skew_threshold": {"type": "number", "default": 0.03}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        chain, expiry, _ = _profile(ctx)
        if chain is None:
            return flat(self, ctx, "insufficient_data", "No chain.", "options")
        sk = om.put_call_skew(chain, expiry)
        if sk is None:
            return flat(
                self, ctx, "insufficient_data", "Skew unavailable (missing IVs).", "options"
            )
        elevated = sk.skew >= self.params["skew_threshold"]
        return make_result(
            self,
            ctx,
            triggered=elevated,
            direction=Side.SHORT if elevated else None,
            score=min(1.0, sk.skew / (self.params["skew_threshold"] * 3)) if elevated else 0.0,
            classification="put_skew_elevated" if elevated else "skew_normal",
            why=f"Put IV {sk.put_iv:.1%} vs call IV {sk.call_iv:.1%} (skew {sk.skew:+.1%}).",
            why_now=(
                "Elevated put skew signals downside hedging demand / risk-off lean."
                if elevated
                else "Skew is within normal bounds."
            ),
            invalidation=InvalidationRule(description="Skew normalizes", kind="options"),
            evidence_for=[
                ev(
                    EK.OPTIONS,
                    "put_call_skew",
                    round(sk.skew, 4),
                    0.5,
                    Side.SHORT if elevated else Side.NEUTRAL,
                    self.scanner_id,
                )
            ],
        )


class CharmVannaScanner(Scanner):
    scanner_id = "charm_vanna"
    name = "Charm & Vanna Flow"
    description = "Aggregate dealer charm/vanna pressure (time-decay & IV-driven hedging drift)."
    category = "options_gamma"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        chain, expiry, _ = _profile(ctx)
        if chain is None:
            return flat(self, ctx, "insufficient_data", "No chain.", "options")
        t = om.years_to_expiry(chain.as_of, expiry)
        gp = om.aggregate_charm_vanna(chain, t, expiry)
        if gp is None:
            return flat(self, ctx, "insufficient_data", "Charm/vanna unavailable.", "options")
        direction = Side.LONG if gp.charm > 0 else Side.SHORT
        return make_result(
            self,
            ctx,
            triggered=abs(gp.charm) > 0,
            direction=direction,
            score=0.4,
            classification="charm_vanna_drift",
            why="Aggregate charm/vanna implies a late-session hedging drift.",
            why_now=f"Net charm {gp.charm:,.0f}, net vanna {gp.vanna:,.0f}.",
            invalidation=InvalidationRule(
                description="IV regime / time-decay assumptions change", kind="options"
            ),
            evidence_for=[
                ev(EK.OPTIONS, "net_charm", round(gp.charm, 0), 0.4, direction, self.scanner_id),
                ev(EK.OPTIONS, "net_vanna", round(gp.vanna, 0), 0.3, direction, self.scanner_id),
            ],
        )


class OptionsFlowScanner(Scanner):
    scanner_id = "options_flow"
    name = "Options Flow & Unusual Activity"
    description = "Strikes where volume far exceeds open interest (fresh positioning)."
    category = "options_gamma"
    default_params = {"vol_oi_ratio": 1.5}
    params_schema = {
        "type": "object",
        "properties": {"vol_oi_ratio": {"type": "number", "default": 1.5}},
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        chain, expiry, _ = _profile(ctx)
        if chain is None:
            return flat(self, ctx, "insufficient_data", "No chain.", "options")
        ratio = self.params["vol_oi_ratio"]
        call_v = put_v = 0
        unusual = 0
        for c in chain.for_expiry(expiry):
            if c.open_interest > 0 and c.volume > ratio * c.open_interest and c.volume > 100:
                unusual += 1
                if c.right == OptionRight.CALL:
                    call_v += c.volume
                else:
                    put_v += c.volume
        if unusual == 0 or (call_v + put_v) == 0:
            return flat(self, ctx, "no_flow", "No unusual options activity.", "options")
        direction = Side.LONG if call_v >= put_v else Side.SHORT
        dominance = max(call_v, put_v) / (call_v + put_v)
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=direction,
            score=min(1.0, dominance),
            classification="unusual_calls" if direction == Side.LONG else "unusual_puts",
            why=f"{unusual} strikes show volume ≫ OI; {'call' if direction == Side.LONG else 'put'} flow dominates.",
            why_now=f"Call vol {call_v:,} vs put vol {put_v:,} on fresh-positioning strikes.",
            invalidation=InvalidationRule(
                description="Flow flips to the other side", kind="options"
            ),
            evidence_for=[
                ev(EK.OPTIONS, "unusual_strikes", unusual, 0.4, direction, self.scanner_id),
                ev(
                    EK.OPTIONS,
                    "flow_dominance",
                    round(dominance, 2),
                    0.4,
                    direction,
                    self.scanner_id,
                ),
            ],
        )
