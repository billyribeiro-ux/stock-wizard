"""Self-learning discovery + genetic rule miner + catalyst/news scanner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from engine.features import FeatureFactory
from engine.ml import MinerConfig, discover, mine_rules
from engine.reports import discovery_to_csv, render_discovery_html, render_discovery_pdf
from engine.scanners import ScanContext, build_scanner
from engine.schemas import NewsItem, Side, Timeframe
from tests.conftest import make_ohlcv

NOW = datetime(2026, 6, 11, 15, 30, tzinfo=UTC)


# ---------- discovery ----------
def test_discovery_finds_turns_and_reasons():
    # Big zig-zag amplitude so pivots clear the min-move filter.
    ohlcv = make_ohlcv(n=500, drift=0.02, amp=4.0)
    report = discover(ohlcv, swing_k=3, min_move_atr=1.0)
    assert report is not None
    assert report.n_events > 0
    assert report.n_bought + report.n_sold == report.n_events
    for e in report.events:
        assert e.kind in {"bought", "sold"}
        assert len(e.reasons) >= 1  # always self-identifies at least one reason
    # bought events should have positive forward moves by construction
    bought = [e for e in report.events if e.kind == "bought"]
    assert all(e.forward_move_pct >= 0 for e in bought)


def test_discovery_reason_stats_aggregate():
    report = discover(make_ohlcv(n=500, drift=0.02, amp=4.0), swing_k=3, min_move_atr=1.0)
    assert report is not None
    for stats, n in ((report.buy_reasons, report.n_bought), (report.sell_reasons, report.n_sold)):
        for s in stats:
            assert 0 < s.count <= n
            assert 0.0 < s.pct_of_events <= 1.0


def test_discovery_validation_and_lift():
    """Discovery must compute baseline-relative lift and an out-of-sample check."""
    report = discover(
        make_ohlcv(n=700, drift=0.02, amp=4.0), swing_k=3, min_move_atr=1.0, train_frac=0.6
    )
    assert report is not None
    assert report.validated_split == 0.6
    assert report.baseline_buy_move >= 0
    for s in report.buy_reasons + report.sell_reasons:
        # lift is avg move minus the in-sample baseline
        assert abs((s.avg_forward_move_pct - s.baseline_move_pct) - s.lift) < 1e-6
        assert isinstance(s.holds_up, bool)
        # validated reasons require a positive out-of-sample lift
        if s.holds_up:
            assert s.oos_lift > 0 and s.lift > 0 and s.oos_count >= 3
    # reasons are ranked with validated ones first
    flags = [s.holds_up for s in report.buy_reasons]
    assert flags == sorted(flags, reverse=True)


def test_discovery_suggested_rules_are_runnable():
    """Validated reasons become custom_rule candidates (loop closure)."""
    report = discover(make_ohlcv(n=800, drift=0.02, amp=4.0), swing_k=3, min_move_atr=1.0)
    assert report is not None
    for sr in report.suggested_rules:
        assert sr.direction in {"LONG", "SHORT"}
        assert sr.conditions and all(
            {"feature", "op", "threshold"} <= set(c) for c in sr.conditions
        )
        assert sr.oos_lift > 0  # only validated reasons are promoted
    # a suggested rule must actually run through the custom_rule scanner
    if report.suggested_rules:
        from engine.features import FeatureFactory
        from engine.scanners import ScanContext, build_scanner

        sr = report.suggested_rules[0]
        ohlcv = make_ohlcv(n=200)
        ctx = ScanContext(
            symbol="X",
            timeframe=ohlcv.timeframe,
            snapshot=FeatureFactory().build_snapshot(ohlcv),
            ohlcv=ohlcv,
            params={"direction": sr.direction, "conditions": sr.conditions},
        )
        res = build_scanner("custom_rule", ctx.params).run(ctx)
        assert res.scanner_id == "custom_rule"


def test_discovery_trade_style_mapping():
    scalp = discover(make_ohlcv(n=300, amp=3.0, timeframe=Timeframe.M5), min_move_atr=1.0)
    swing = discover(make_ohlcv(n=300, amp=3.0, timeframe=Timeframe.D1), min_move_atr=1.0)
    assert scalp is not None and scalp.trade_style == "scalping"
    assert swing is not None and swing.trade_style == "swing"


def test_discovery_insufficient_history():
    assert discover(make_ohlcv(n=20)) is None


def test_discovery_csv_and_pdf_export():
    report = discover(make_ohlcv(n=400, amp=4.0), min_move_atr=1.0)
    assert report is not None
    csv_text = discovery_to_csv(report)
    assert csv_text.splitlines()[0].startswith("ts,kind,price")
    assert len(csv_text.splitlines()) == report.n_events + 1
    html = render_discovery_html(report)
    assert "Why it was BOUGHT" in html and "Why it was SOLD" in html
    pdf = render_discovery_pdf(report)
    assert pdf[:5] == b"%PDF-"


# ---------- genetic miner ----------
def test_genetic_miner_evolves_rules():
    ohlcv = make_ohlcv(n=500, drift=0.05, amp=2.0)
    rules = mine_rules(
        ohlcv, horizon=10, config=MinerConfig(population=24, generations=8, min_hits=10, top_n=5)
    )
    # On synthetic data rules may or may not be found, but the contract must hold.
    for r in rules:
        assert r.description.startswith(("LONG when", "SHORT when"))
        assert r.train_hits >= 10
        assert isinstance(r.holds_up, bool)


def test_genetic_miner_insufficient_history():
    assert mine_rules(make_ohlcv(n=60)) == []


# ---------- catalyst/news scanner ----------
def _news_ctx(news):
    snap = FeatureFactory().build_snapshot(make_ohlcv())
    return ScanContext(
        symbol="AAPL",
        timeframe=Timeframe.D1,
        snapshot=snap,
        ohlcv=make_ohlcv(),
        news=news,
        as_of=NOW,
    )


def test_catalyst_news_bullish():
    news = [
        NewsItem(
            symbol="AAPL",
            headline="Apple beats estimates, raises guidance",
            published_at=NOW - timedelta(hours=3),
        )
    ]
    res = build_scanner("catalyst_news").run(_news_ctx(news))
    assert res.triggered and res.direction == Side.LONG
    assert res.classification == "catalyst_bullish"


def test_catalyst_news_bearish():
    news = [
        NewsItem(
            symbol="AAPL",
            headline="Apple misses on revenue; shares plunge after downgrade",
            published_at=NOW - timedelta(hours=5),
        )
    ]
    res = build_scanner("catalyst_news").run(_news_ctx(news))
    assert res.triggered and res.direction == Side.SHORT


def test_catalyst_news_no_data():
    res = build_scanner("catalyst_news").run(_news_ctx([]))
    assert not res.triggered and res.classification == "no_news_data"


def test_catalyst_news_stale_headlines_flow_driven():
    news = [
        NewsItem(
            symbol="AAPL", headline="Apple beats estimates", published_at=NOW - timedelta(days=10)
        )
    ]
    res = build_scanner("catalyst_news").run(_news_ctx(news))
    assert res.classification == "flow_driven"
