"""BIST market hours utilities.

Provides functions to check if the Turkish stock market (BIST) is open
for trading based on Istanbul timezone and standard trading hours.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# BIST timezone
ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")

# BIST standard trading hours
# Morning session: 10:00 - 13:00
# Afternoon session: 14:00 - 18:00
# For simplicity, we treat it as continuous 10:00 - 18:00
MARKET_OPEN_TIME = time(10, 0)  # 10:00
MARKET_CLOSE_TIME = time(18, 0)  # 18:00

# Turkish public holidays for 2026 (hardcoded for simplicity)
# TODO: Move to database or external calendar service
TURKISH_HOLIDAYS_2026: set[date] = {
    # New Year's Day
    date(2026, 1, 1),
    # National Sovereignty and Children's Day
    date(2026, 4, 23),
    # Labor Day
    date(2026, 5, 1),
    # Commemoration of Atatürk, Youth and Sports Day
    date(2026, 5, 19),
    # Democracy and National Unity Day
    date(2026, 7, 15),
    # Victory Day
    date(2026, 8, 30),
    # Republic Day
    date(2026, 10, 29),
    # Religious holidays (approximate - should be updated each year)
    # Eid al-Fitr (Ramazan Bayramı) - 3 days
    date(2026, 3, 22),
    date(2026, 3, 23),
    date(2026, 3, 24),
    # Eid al-Adha (Kurban Bayramı) - 4 days
    date(2026, 5, 28),
    date(2026, 5, 29),
    date(2026, 5, 30),
    date(2026, 5, 31),
}


def is_bist_business_day(dt: datetime | date) -> bool:
    """Check if a date is a BIST business day.

    A business day is a weekday (Monday-Friday) that is not a public holiday.

    Args:
        dt: Datetime or date to check. If datetime, will be converted to Istanbul timezone.

    Returns:
        True if it's a business day, False otherwise.

    Example:
        >>> from datetime import date
        >>> is_bist_business_day(date(2026, 4, 6))  # Monday
        True
        >>> is_bist_business_day(date(2026, 4, 5))  # Sunday
        False
    """
    # Convert to date if datetime
    if isinstance(dt, datetime):
        dt = dt.date()

    # Weekend check
    if dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False

    # Holiday check
    if dt in TURKISH_HOLIDAYS_2026:
        return False

    return True


def is_bist_trading_hours(dt: datetime | None = None) -> bool:
    """Check if BIST is currently in trading hours.

    Trading hours are 10:00 - 18:00 Istanbul time on business days.

    Args:
        dt: Datetime to check. If None, uses current time.
            Timezone-naive datetimes are assumed to be UTC.

    Returns:
        True if market is open, False otherwise.

    Example:
        >>> from datetime import datetime, timezone
        >>> # Monday 11:00 Istanbul time
        >>> dt = datetime(2026, 4, 6, 8, 0, tzinfo=timezone.utc)  # 11:00 Istanbul
        >>> is_bist_trading_hours(dt)
        True
    """
    if dt is None:
        dt = datetime.now(ISTANBUL_TZ)
    elif dt.tzinfo is None:
        # Assume UTC for naive datetimes
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    # Convert to Istanbul timezone
    dt_istanbul = dt.astimezone(ISTANBUL_TZ)

    # Check business day
    if not is_bist_business_day(dt_istanbul.date()):
        return False

    # Check trading hours
    current_time = dt_istanbul.time()
    return MARKET_OPEN_TIME <= current_time < MARKET_CLOSE_TIME


def get_next_trading_day(dt: datetime | date) -> date:
    """Get the next BIST trading day.

    Args:
        dt: Starting date. If datetime, date portion is used.

    Returns:
        Next trading day (could be the same day if input is after market close).

    Example:
        >>> from datetime import date
        >>> get_next_trading_day(date(2026, 4, 6))  # Monday
        datetime.date(2026, 4, 7)
        >>> get_next_trading_day(date(2026, 4, 10))  # Friday
        datetime.date(2026, 4, 13)  # Monday
    """
    # Convert to date if datetime
    if isinstance(dt, datetime):
        dt = dt.date()

    # Check if today is still a trading day with time remaining
    now = datetime.now(ISTANBUL_TZ)
    if dt == now.date() and now.time() < MARKET_CLOSE_TIME:
        if is_bist_business_day(dt):
            return dt

    # Find next trading day
    next_day = dt + timedelta(days=1)
    while not is_bist_business_day(next_day):
        next_day += timedelta(days=1)
        # Safety limit
        if (next_day - dt).days > 30:
            break

    return next_day


def get_market_status(dt: datetime | None = None) -> dict:
    """Get detailed market status.

    Args:
        dt: Datetime to check. If None, uses current time.

    Returns:
        Dict with market status details.

    Example:
        >>> get_market_status()
        {
            "is_open": True,
            "is_business_day": True,
            "current_time": "11:30",
            "market_open": "10:00",
            "market_close": "18:00",
            "next_trading_day": "2026-04-07"
        }
    """
    if dt is None:
        dt = datetime.now(ISTANBUL_TZ)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    dt_istanbul = dt.astimezone(ISTANBUL_TZ)
    is_business_day = is_bist_business_day(dt_istanbul.date())

    return {
        "is_open": is_bist_trading_hours(dt_istanbul),
        "is_business_day": is_business_day,
        "current_time": dt_istanbul.strftime("%H:%M"),
        "market_open": MARKET_OPEN_TIME.strftime("%H:%M"),
        "market_close": MARKET_CLOSE_TIME.strftime("%H:%M"),
        "timezone": "Europe/Istanbul",
        "next_trading_day": get_next_trading_day(dt_istanbul).isoformat(),
    }