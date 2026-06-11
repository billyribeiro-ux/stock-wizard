"""Emit a combined JSON Schema for the canonical contracts.

Used by ``just gen-types`` to generate TypeScript types for the SvelteKit dashboard,
guaranteeing the Python engine and the UI never drift. Run as:

    python -m engine.schemas.export_jsonschema > apps/web/src/lib/contracts.schema.json
"""

from __future__ import annotations

import json
import sys

from pydantic import TypeAdapter

from .backtest import BacktestResult
from .features import FeatureSnapshot
from .market import OHLCV, MarketBar
from .options import OptionChain
from .report import ReportSpec
from .scanner import ScannerResult, ScannerSpec
from .signal import SignalPacket

_MODELS = [
    MarketBar,
    OHLCV,
    OptionChain,
    FeatureSnapshot,
    ScannerResult,
    ScannerSpec,
    SignalPacket,
    BacktestResult,
    ReportSpec,
]


def build_schema() -> dict:
    """Return a JSON Schema document with one definition per top-level model."""
    defs: dict = {}
    for model in _MODELS:
        schema = TypeAdapter(model).json_schema(ref_template="#/$defs/{model}")
        nested = schema.pop("$defs", {})
        defs.update(nested)
        defs[model.__name__] = schema
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "StockWizardContracts",
        "$defs": defs,
    }


def main() -> None:
    json.dump(build_schema(), sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
