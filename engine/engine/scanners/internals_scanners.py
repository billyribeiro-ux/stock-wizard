"""Institutional market-internals scanners (§6.3) — computed from constituents.

These read a universe basket (ctx.aux) the way institutional desks compute internals:
advance/decline & A/D line, UVOL/DVOL/VOLD, TRIN (Arms Index), McClellan oscillator &
summation, % above 20/50/200MA participation, net new highs/lows, Zweig breadth
thrust, put/call ratio (from the live chain), VIX term structure, and the classic
risk-appetite ratio complex (RSP/SPY, SPHB/SPLV, XLY/XLP, IWM/SPY, HYG/IEF).
"""

from __future__ import annotations

from ..features import internals as mi
from ..schemas import EvidenceKind as EK
from ..schemas import InvalidationRule, ScannerResult, Side
from ._common import ev, flat, make_result
from .base import ScanContext, Scanner


def _breadth(ctx: ScanContext) -> mi.BreadthSnapshot | None:
    if not ctx.aux:
        return None
    universe = {s: o for s, o in ctx.aux.items() if not s.startswith("^")}
    return mi.compute_breadth(universe)


class MarketBreadthScanner(Scanner):
    scanner_id = "market_breadth"
    name = "Market Internals Breadth"
    description = "A/D, A/D line, UVOL/DVOL and VOLD computed over the universe basket."
    category = "internals"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        b = _breadth(ctx)
        if b is None:
            return flat(self, ctx, "no_universe_data", "Universe basket unavailable.", "internals")
        breadth_pct = b.advancers / max(b.n_symbols, 1)
        strong = breadth_pct >= 0.65 and b.vold > 0
        weak = breadth_pct <= 0.35 and b.vold < 0
        direction = Side.LONG if strong else Side.SHORT if weak else Side.NEUTRAL
        return make_result(
            self,
            ctx,
            triggered=strong or weak,
            direction=direction if direction != Side.NEUTRAL else None,
            score=abs(breadth_pct - 0.5) * 2,
            classification="broad_advance"
            if strong
            else "broad_decline"
            if weak
            else "mixed_breadth",
            why=(
                f"{b.advancers}/{b.n_symbols} advancing (A/D {b.ad_ratio}); "
                f"UVOL {b.uvol:,.0f} vs DVOL {b.dvol:,.0f} (VOLD {b.vold:+,.0f})."
            ),
            why_now="Internals confirm the move."
            if (strong or weak)
            else "Internals are mixed — no confirmation.",
            invalidation=InvalidationRule(description="Breadth flips sides", kind="internals"),
            evidence_for=[
                ev(
                    EK.INTERNAL,
                    "advancers_pct",
                    round(breadth_pct, 2),
                    0.5,
                    direction,
                    self.scanner_id,
                ),
                ev(EK.INTERNAL, "vold", round(b.vold, 0), 0.35, direction, self.scanner_id),
            ],
            feature_refs={
                "advancers": float(b.advancers),
                "decliners": float(b.decliners),
                "uvol": b.uvol,
                "dvol": b.dvol,
                "vold": b.vold,
            },
        )


class ArmsTrinScanner(Scanner):
    scanner_id = "arms_trin"
    name = "TRIN & VOLD Confirmation (Arms Index)"
    description = "TRIN = (ADV/DECN)/(UVOL/DVOL). <0.8 bullish pressure, >1.2 selling pressure, >2 capitulation."
    category = "internals"
    default_params = {"bull": 0.8, "bear": 1.2, "capitulation": 2.0}
    params_schema = {
        "type": "object",
        "properties": {
            "bull": {"type": "number", "default": 0.8},
            "bear": {"type": "number", "default": 1.2},
            "capitulation": {"type": "number", "default": 2.0},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        b = _breadth(ctx)
        if b is None or b.trin is None:
            return flat(self, ctx, "no_universe_data", "TRIN unavailable.", "internals")
        trin = b.trin
        if trin >= self.params["capitulation"]:
            cls, direction, why_now = (
                "capitulation",
                Side.LONG,
                f"TRIN {trin} — panic selling concentrated in decliners; contrarian bottom fuel.",
            )
        elif trin <= self.params["bull"]:
            cls, direction, why_now = (
                "buying_pressure",
                Side.LONG,
                f"TRIN {trin} — volume concentrating in advancers.",
            )
        elif trin >= self.params["bear"]:
            cls, direction, why_now = (
                "selling_pressure",
                Side.SHORT,
                f"TRIN {trin} — volume concentrating in decliners.",
            )
        else:
            return make_result(
                self,
                ctx,
                triggered=False,
                direction=None,
                score=0.3,
                classification="trin_neutral",
                why=f"TRIN {trin} in the neutral band.",
                why_now="No internals edge from TRIN.",
                invalidation=InvalidationRule(
                    description="TRIN leaves the neutral band", kind="internals"
                ),
            )
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=direction,
            score=min(1.0, abs(trin - 1.0)),
            classification=cls,
            why=f"Arms Index (TRIN) {trin} on A/D {b.ad_ratio} with UVOL/DVOL {b.uvol / max(b.dvol, 1):.2f}.",
            why_now=why_now,
            invalidation=InvalidationRule(
                description="TRIN normalizes toward 1.0", kind="internals"
            ),
            evidence_for=[ev(EK.INTERNAL, "trin", trin, 0.6, direction, self.scanner_id)],
            feature_refs={"trin": trin},
        )


class McClellanScanner(Scanner):
    scanner_id = "mcclellan"
    name = "McClellan Oscillator & Summation"
    description = "EMA19-EMA39 of net advances; oversold/overbought thrusts and summation trend."
    category = "internals"
    default_params = {"overbought": 70.0, "oversold": -70.0}
    params_schema = {
        "type": "object",
        "properties": {
            "overbought": {"type": "number", "default": 70.0},
            "oversold": {"type": "number", "default": -70.0},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        b = _breadth(ctx)
        if b is None or b.mcclellan_osc is None:
            return flat(
                self,
                ctx,
                "no_universe_data",
                "McClellan unavailable (needs ~40 bars).",
                "internals",
            )
        osc = b.mcclellan_osc
        if osc <= self.params["oversold"]:
            direction, cls = Side.LONG, "mcclellan_oversold"
            why_now = f"Oscillator {osc:+.0f} — washed-out breadth, snapback zone."
        elif osc >= self.params["overbought"]:
            direction, cls = Side.SHORT, "mcclellan_overbought"
            why_now = f"Oscillator {osc:+.0f} — stretched breadth, digestion likely."
        else:
            direction = Side.LONG if osc > 0 else Side.SHORT
            cls = "mcclellan_positive" if osc > 0 else "mcclellan_negative"
            why_now = (
                f"Oscillator {osc:+.0f} — breadth momentum {'positive' if osc > 0 else 'negative'}."
            )
        return make_result(
            self,
            ctx,
            triggered=abs(osc) >= 30,
            direction=direction,
            score=min(1.0, abs(osc) / 150),
            classification=cls,
            why=f"McClellan oscillator {osc:+.0f}, summation {b.mcclellan_sum:+.0f}.",
            why_now=why_now,
            invalidation=InvalidationRule(
                description="Oscillator crosses zero the other way", kind="internals"
            ),
            evidence_for=[
                ev(EK.INTERNAL, "mcclellan_osc", osc, 0.55, direction, self.scanner_id),
                ev(EK.INTERNAL, "mcclellan_sum", b.mcclellan_sum, 0.3, direction, self.scanner_id),
            ],
            feature_refs={"mcclellan_osc": osc, "mcclellan_sum": b.mcclellan_sum or 0.0},
        )


class PercentAboveMAScanner(Scanner):
    scanner_id = "pct_above_ma"
    name = "% Above Moving Averages"
    description = "Participation breadth: % of the universe above 20/50/200-bar MAs."
    category = "internals"
    default_params = {"washout": 0.2, "euphoria": 0.85}
    params_schema = {
        "type": "object",
        "properties": {
            "washout": {"type": "number", "default": 0.2},
            "euphoria": {"type": "number", "default": 0.85},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        b = _breadth(ctx)
        if b is None or b.pct_above_ma50 is None:
            return flat(self, ctx, "no_universe_data", "MA breadth unavailable.", "internals")
        p20, p50, p200 = b.pct_above_ma20, b.pct_above_ma50, b.pct_above_ma200
        if p50 <= self.params["washout"]:
            direction, cls = Side.LONG, "participation_washout"
            why_now = f"Only {p50:.0%} above the 50MA — historically a mean-reversion zone."
        elif p50 >= self.params["euphoria"]:
            direction, cls = Side.SHORT, "participation_euphoria"
            why_now = f"{p50:.0%} above the 50MA — crowded participation, chase risk."
        else:
            direction = Side.LONG if p50 >= 0.5 else Side.SHORT
            cls = "healthy_participation" if p50 >= 0.5 else "weak_participation"
            why_now = f"{p50:.0%} above the 50MA."
        return make_result(
            self,
            ctx,
            triggered=p50 <= self.params["washout"] or p50 >= self.params["euphoria"],
            direction=direction,
            score=abs(p50 - 0.5) * 2,
            classification=cls,
            why=f"Above-MA breadth: 20MA {p20:.0%} / 50MA {p50:.0%} / 200MA {p200 if p200 is None else f'{p200:.0%}'}.",
            why_now=why_now,
            invalidation=InvalidationRule(description="Participation normalizes", kind="internals"),
            evidence_for=[
                ev(EK.INTERNAL, "pct_above_50ma", round(p50, 2), 0.5, direction, self.scanner_id)
            ],
            feature_refs={
                "pct_above_ma20": p20 or 0.0,
                "pct_above_ma50": p50,
                "pct_above_ma200": p200 or 0.0,
            },
        )


class NewHighsLowsScanner(Scanner):
    scanner_id = "nh_nl"
    name = "Net New Highs / New Lows"
    description = "Net 52-week (rolling-window) new highs minus new lows across the universe."
    category = "internals"
    default_params = {"min_net": 3}
    params_schema = {"type": "object", "properties": {"min_net": {"type": "integer", "default": 3}}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        b = _breadth(ctx)
        if b is None:
            return flat(self, ctx, "no_universe_data", "NH-NL unavailable.", "internals")
        net = b.net_new_highs
        if abs(net) < self.params["min_net"]:
            return flat(
                self, ctx, "nhnl_neutral", f"Net new highs {net:+d} — no expansion.", "internals"
            )
        direction = Side.LONG if net > 0 else Side.SHORT
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=direction,
            score=min(1.0, abs(net) / max(b.n_symbols * 0.3, 1)),
            classification="nh_expansion" if net > 0 else "nl_expansion",
            why=f"Net new highs {net:+d} across {b.n_symbols} names.",
            why_now=(
                "New highs expanding — leadership broadening."
                if net > 0
                else "New lows expanding — deterioration under the surface."
            ),
            invalidation=InvalidationRule(description="NH-NL flips sign", kind="internals"),
            evidence_for=[ev(EK.INTERNAL, "net_new_highs", net, 0.55, direction, self.scanner_id)],
            feature_refs={"net_new_highs": float(net)},
        )


class ZweigThrustScanner(Scanner):
    scanner_id = "zweig_thrust"
    name = "Zweig Breadth Thrust"
    description = (
        "10-bar EMA of adv/(adv+dec) surging from <0.40 to >0.615 — a rare powerful buy thrust."
    )
    category = "internals"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        b = _breadth(ctx)
        if b is None or b.zweig_emaratio is None:
            return flat(self, ctx, "no_universe_data", "Zweig ratio unavailable.", "internals")
        if b.zweig_thrust:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.LONG,
                score=0.9,
                classification="breadth_thrust",
                why=f"Zweig breadth thrust fired (EMA ratio {b.zweig_emaratio}).",
                why_now="From washed-out to surging breadth inside 10 bars — historically one of "
                "the strongest bullish internals signals.",
                invalidation=InvalidationRule(
                    description="Thrust fails (ratio rolls back under 0.5)", kind="internals"
                ),
                evidence_for=[
                    ev(
                        EK.INTERNAL,
                        "zweig_ratio",
                        b.zweig_emaratio,
                        0.9,
                        Side.LONG,
                        self.scanner_id,
                    )
                ],
            )
        return make_result(
            self,
            ctx,
            triggered=False,
            direction=None,
            score=0.3,
            classification="no_thrust",
            why=f"Zweig EMA ratio {b.zweig_emaratio} — no thrust condition.",
            why_now="Monitoring for a <0.40 → >0.615 surge.",
            invalidation=InvalidationRule(description="n/a", kind="internals"),
        )


class PutCallRatioScanner(Scanner):
    scanner_id = "put_call_ratio"
    name = "Put/Call Ratio"
    description = "Volume-based put/call from the live chain; extremes are contrarian."
    category = "internals"
    default_params = {"fear": 1.2, "greed": 0.6}
    params_schema = {
        "type": "object",
        "properties": {
            "fear": {"type": "number", "default": 1.2},
            "greed": {"type": "number", "default": 0.6},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        if ctx.chain is None:
            return flat(self, ctx, "no_chain", "Needs an option chain.", "options")
        pc = mi.put_call_ratio(ctx.chain)
        if pc is None:
            return flat(self, ctx, "no_volume", "No option volume to compute P/C.", "options")
        if pc.volume_pc >= self.params["fear"]:
            direction, cls = Side.LONG, "pc_fear_extreme"
            why_now = f"P/C {pc.volume_pc} — heavy put buying; contrarian bullish at extremes."
        elif pc.volume_pc <= self.params["greed"]:
            direction, cls = Side.SHORT, "pc_greed_extreme"
            why_now = f"P/C {pc.volume_pc} — call chasing; contrarian bearish at extremes."
        else:
            return make_result(
                self,
                ctx,
                triggered=False,
                direction=None,
                score=0.3,
                classification="pc_neutral",
                why=f"Put/Call {pc.volume_pc} (OI P/C {pc.oi_pc}).",
                why_now="No sentiment extreme.",
                invalidation=InvalidationRule(description="P/C reaches an extreme", kind="options"),
            )
        return make_result(
            self,
            ctx,
            triggered=True,
            direction=direction,
            score=min(1.0, abs(pc.volume_pc - 0.9)),
            classification=cls,
            why=f"Put/Call volume ratio {pc.volume_pc} (puts {pc.put_volume:,} vs calls {pc.call_volume:,}; OI P/C {pc.oi_pc}).",
            why_now=why_now,
            invalidation=InvalidationRule(description="P/C normalizes toward ~0.9", kind="options"),
            evidence_for=[
                ev(EK.OPTIONS, "put_call_volume", pc.volume_pc, 0.55, direction, self.scanner_id)
            ],
            feature_refs={"put_call_volume": pc.volume_pc, "put_call_oi": pc.oi_pc},
        )


class VixTermStructureScanner(Scanner):
    scanner_id = "vix_term_structure"
    name = "VIX Term Structure"
    description = (
        "VIX9D/VIX/VIX3M: contango = calm; backwardation = acute stress (institutional staple)."
    )
    category = "internals"
    default_params = {}
    params_schema = {"type": "object", "properties": {}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        ts = mi.vix_term_structure(ctx.aux)
        if ts is None:
            return flat(self, ctx, "no_vix_data", "VIX complex unavailable.", "internals")
        if ts.backwardation:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=min(1.0, (ts.term_ratio - 1.0) * 4 + 0.5),
                classification="backwardation",
                why=f"VIX {ts.vix} > VIX3M {ts.vix3m} (ratio {ts.term_ratio}) — curve inverted.",
                why_now="Backwardation = the market pays up for *near-term* protection: acute stress.",
                invalidation=InvalidationRule(
                    description="Curve returns to contango", kind="internals"
                ),
                evidence_for=[
                    ev(
                        EK.INTERNAL,
                        "vix_term_ratio",
                        ts.term_ratio,
                        0.7,
                        Side.SHORT,
                        self.scanner_id,
                    )
                ],
                feature_refs={"vix": ts.vix or 0.0, "term_ratio": ts.term_ratio or 0.0},
            )
        steep = ts.term_ratio is not None and ts.term_ratio < 0.85
        return make_result(
            self,
            ctx,
            triggered=steep,
            direction=Side.LONG if steep else None,
            score=0.5 if steep else 0.3,
            classification="steep_contango" if steep else "normal_contango",
            why=f"VIX9D {ts.vix9d} / VIX {ts.vix} / VIX3M {ts.vix3m} (term ratio {ts.term_ratio}).",
            why_now=(
                "Steep contango — vol sellers in control, supportive for equities."
                if steep
                else "Normal contango — calm regime."
            ),
            invalidation=InvalidationRule(description="Curve flattens/inverts", kind="internals"),
            evidence_for=[
                ev(
                    EK.INTERNAL,
                    "vix_term_ratio",
                    ts.term_ratio or 0.0,
                    0.4,
                    Side.LONG if steep else Side.NEUTRAL,
                    self.scanner_id,
                )
            ],
            feature_refs={"vix": ts.vix or 0.0, "term_ratio": ts.term_ratio or 0.0},
        )


class AbsorptionRatioScanner(Scanner):
    scanner_id = "absorption_ratio"
    name = "Absorption Ratio (Systemic Risk)"
    description = (
        "Kritzman-Lo PCA systemic-risk gauge: share of universe variance in the top "
        "eigenvectors. A spike in coupling (standardized shift >1σ) flags fragility."
    )
    category = "internals"
    default_params = {"window": 60, "frac": 0.2}
    params_schema = {
        "type": "object",
        "properties": {
            "window": {"type": "integer", "default": 60},
            "frac": {"type": "number", "default": 0.2},
        },
    }

    def run(self, ctx: ScanContext) -> ScannerResult:
        from ..ml import compute_absorption

        universe = {s: o for s, o in ctx.aux.items() if not s.startswith("^")}
        res = compute_absorption(universe, int(self.params["window"]), float(self.params["frac"]))
        if res is None:
            return flat(
                self, ctx, "no_universe_data", "Universe basket unavailable for PCA.", "internals"
            )
        if res.elevated:
            return make_result(
                self,
                ctx,
                triggered=True,
                direction=Side.SHORT,
                score=min(1.0, 0.5 + res.standardized_shift / 4),
                classification="fragility_warning",
                why=(
                    f"Absorption ratio {res.absorption_ratio:.0%} of variance in "
                    f"{res.n_components}/{res.n_assets} components — market tightly coupled."
                ),
                why_now=(
                    f"AR standardized shift {res.standardized_shift:+.1f}σ — coupling spiked, "
                    f"a Kritzman-Lo fragility/drawdown precursor."
                ),
                invalidation=InvalidationRule(
                    description="Coupling relaxes (shift falls < 0)", kind="internals"
                ),
                evidence_for=[
                    ev(
                        EK.INTERNAL,
                        "absorption_ratio",
                        res.absorption_ratio,
                        0.5,
                        Side.SHORT,
                        self.scanner_id,
                    ),
                    ev(
                        EK.INTERNAL,
                        "ar_std_shift",
                        res.standardized_shift,
                        0.4,
                        Side.SHORT,
                        self.scanner_id,
                    ),
                ],
                feature_refs={
                    "absorption_ratio": res.absorption_ratio,
                    "ar_std_shift": res.standardized_shift,
                },
            )
        return make_result(
            self,
            ctx,
            triggered=False,
            direction=None,
            score=0.3,
            classification="coupling_normal",
            why=f"Absorption ratio {res.absorption_ratio:.0%} (shift {res.standardized_shift:+.1f}σ).",
            why_now="Market coupling is within its normal band.",
            invalidation=InvalidationRule(description="Coupling spikes >1σ", kind="internals"),
            feature_refs={
                "absorption_ratio": res.absorption_ratio,
                "ar_std_shift": res.standardized_shift,
            },
        )


class RiskAppetiteScanner(Scanner):
    scanner_id = "risk_appetite"
    name = "Risk-Appetite Ratio Complex"
    description = (
        "RSP/SPY, SPHB/SPLV, XLY/XLP, IWM/SPY, HYG/IEF momentum — the institutional risk dial."
    )
    category = "internals"
    default_params = {"window": 20}
    params_schema = {"type": "object", "properties": {"window": {"type": "integer", "default": 20}}}

    def run(self, ctx: ScanContext) -> ScannerResult:
        window = int(self.params["window"])
        readings: list[tuple[str, float]] = []
        for a, b_sym, label in mi.RISK_RATIO_PAIRS:
            m = mi.ratio_momentum(ctx.aux.get(a), ctx.aux.get(b_sym), window)
            if m is not None:
                readings.append((label, m))
        if len(readings) < 2:
            return flat(self, ctx, "no_ratio_data", "Risk-ratio pairs unavailable.", "internals")
        risk_on = sum(1 for _, m in readings if m > 0)
        frac = risk_on / len(readings)
        direction = Side.LONG if frac >= 0.5 else Side.SHORT
        detail = ", ".join(f"{label} {m:+.1%}" for label, m in readings)
        return make_result(
            self,
            ctx,
            triggered=frac >= 0.75 or frac <= 0.25,
            direction=direction,
            score=abs(frac - 0.5) * 2,
            classification="risk_on_broad"
            if frac >= 0.75
            else "risk_off_broad"
            if frac <= 0.25
            else "risk_mixed",
            why=f"{risk_on}/{len(readings)} risk ratios positive over {window} bars.",
            why_now=detail,
            invalidation=InvalidationRule(description="Ratio complex flips", kind="internals"),
            evidence_for=[
                ev(
                    EK.INTERNAL,
                    label,
                    round(m, 4),
                    0.6 / len(readings),
                    Side.LONG if m > 0 else Side.SHORT,
                    self.scanner_id,
                )
                for label, m in readings
            ],
            feature_refs=dict(readings),
        )
