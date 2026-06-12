"""arq worker — runs scans, backtests, ML jobs, and exports off the request path."""

from __future__ import annotations

from arq.connections import RedisSettings

from common.settings import get_settings

from .tasks import run_backtest, run_discovery, run_scan, train_model

_settings = get_settings()


class WorkerSettings:
    functions = [run_scan, run_backtest, train_model, run_discovery]
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    max_jobs = 10
    job_timeout = 600
