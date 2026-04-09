"""Pipeline services for data ingestion and scheduling."""

from app.services.pipeline.scheduler import (
    scheduler,
    start_scheduler,
    stop_scheduler,
    get_scheduler_status,
    run_price_sync_job,
    run_financials_weekly_job,
    run_financials_reporting_job,
    run_kap_hourly_job,
    run_kap_watchlist_daily_job,
    run_kap_slow_job,
)
from app.services.pipeline.market_hours import (
    is_bist_business_day,
    is_bist_trading_hours,
    get_next_trading_day,
    get_market_status,
)
from app.services.pipeline.job_policy import (
    get_all_active_symbols,
    get_bist100_symbols_from_provider,
    get_watchlist_symbols,
    get_slow_sync_symbols,
    get_symbols_by_universe,
)

__all__ = [
    # Scheduler
    "scheduler",
    "start_scheduler",
    "stop_scheduler",
    "get_scheduler_status",
    "run_price_sync_job",
    "run_financials_weekly_job",
    "run_financials_reporting_job",
    "run_kap_hourly_job",
    "run_kap_watchlist_daily_job",
    "run_kap_slow_job",
    # Market hours
    "is_bist_business_day",
    "is_bist_trading_hours",
    "get_next_trading_day",
    "get_market_status",
    # Job policy
    "get_all_active_symbols",
    "get_bist100_symbols_from_provider",
    "get_watchlist_symbols",
    "get_slow_sync_symbols",
    "get_symbols_by_universe",
]