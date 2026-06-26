"""Market-internals stub (TICK/TRIN/VOLD/ADD).

yfinance has no internals feed, so v1 ships a stub that returns no data behind the
real InternalsSource interface. A paid vendor (e.g. a CBOE/IEX/Polygon internals feed)
drops in later without touching scanners — they already treat internals as optional
confirming evidence.
"""

from __future__ import annotations

from datetime import datetime

from .base import InternalsBar, InternalsSource

SUPPORTED_METRICS = ["TICK", "TRIN", "VOLD", "ADD", "UVOL", "DVOL"]


class InternalsStub(InternalsSource):
    name = "internals_stub"
    available = False  # signals to scanners that internals confirmation is unavailable

    def get_internals(
        self, metric: str, start: datetime, end: datetime | None = None
    ) -> list[InternalsBar]:
        return []
