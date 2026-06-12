"""PDF export via Jinja2 + WeasyPrint.

HTML/CSS templating means the PDF and future in-app reports share markup. WeasyPrint
is imported lazily so this module loads even where its native libs are absent (the
import only matters when a PDF is actually rendered).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..schemas import BacktestResult, ScannerResult

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml", "j2"]),
)


def render_evidence_html(
    results: list[ScannerResult], title: str = "Stock Wizard — Evidence Report"
) -> str:
    template = _env.get_template("evidence_report.html.j2")
    first = results[0] if results else None
    return template.render(
        title=title,
        results=results,
        symbol=first.symbol if first else "",
        timeframe=first.timeframe.value if first else "",
        scanner_id=first.scanner_id if first else "",
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )


def render_evidence_pdf(
    results: list[ScannerResult], title: str = "Stock Wizard — Evidence Report"
) -> bytes:
    from weasyprint import HTML  # lazy: requires native libs only when rendering

    html = render_evidence_html(results, title)
    return HTML(string=html).write_pdf()


def _money(x) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    return f"{'+' if v > 0 else ''}{v:,.2f}"


def render_backtest_html(
    result: BacktestResult, title: str = "Stock Wizard — Backtest Report"
) -> str:
    m = result.metrics
    stat_cards = [
        ("Trades", str(m.total_trades)),
        ("Win rate", f"{m.win_rate:.0%}"),
        ("Profit factor", f"{m.profit_factor:.2f}"),
        ("Expectancy", _money(m.expectancy)),
        ("Total P/L", _money(m.total_pnl)),
        ("CAGR", f"{m.cagr:+.1%}"),
        ("Sharpe", f"{m.sharpe:.2f}"),
        ("Sortino", f"{m.sortino:.2f}"),
        ("Max DD", f"-{m.max_drawdown:.1%}"),
        ("Avg win", _money(m.avg_win)),
        ("Avg loss", _money(-abs(m.avg_loss))),
        ("Exposure", f"{m.exposure:.0%}"),
    ]
    template = _env.get_template("backtest_report.html.j2")
    return template.render(
        title=title,
        scanner_id=result.scanner_id,
        universe=", ".join(result.universe),
        period_start=result.period_start.isoformat(),
        period_end=result.period_end.isoformat(),
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        stat_cards=stat_cards,
        trades=[t.model_dump(mode="json") for t in result.trades[:25]],
    )


def render_backtest_pdf(
    result: BacktestResult, title: str = "Stock Wizard — Backtest Report"
) -> bytes:
    from weasyprint import HTML

    return HTML(string=render_backtest_html(result, title)).write_pdf()
