"""Stock Wizard quant engine.

Pure, importable domain packages: canonical schemas (contracts), data adapters,
feature factory, scanners, signal/evidence builders, backtesting, reports, and risk.
The FastAPI service and the worker both import from here; the engine itself has no
web or database dependencies.
"""

__version__ = "0.1.0"
