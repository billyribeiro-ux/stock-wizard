"""arq worker — runs scans, backtests, ML jobs, and exports off the request path."""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from common.settings import get_settings

from .tasks import run_backtest, run_discovery, run_roster_validation, run_scan, train_model

_settings = get_settings()


class WorkerSettings:
    functions = [run_scan, run_backtest, train_model, run_discovery, run_roster_validation]
    # Weekly roster re-validation (Sun 02:00 UTC) keeps each scanner's out-of-sample edge
    # weight fresh as regimes shift, without burning compute on every run.
    cron_jobs = [cron(run_roster_validation, weekday="sun", hour=2, minute=0)]
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    max_jobs = 10
    job_timeout = 1800  # roster validation forward-tests the whole basket
