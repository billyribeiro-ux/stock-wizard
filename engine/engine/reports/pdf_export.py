"""PDF export via Jinja2 + WeasyPrint.

HTML/CSS templating means the PDF and future in-app reports share markup. WeasyPrint
is imported lazily so this module loads even where its native libs are absent (the
import only matters when a PDF is actually rendered).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..schemas import ScannerResult

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
