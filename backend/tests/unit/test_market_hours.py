"""Unit tests for market_hours module."""

import pytest
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

from app.services.pipeline.market_hours import (
    is_bist_business_day,
    is_bist_trading_hours,
    get_next_trading_day,
    get_market_status,
    ISTANBUL_TZ,
    MARKET_OPEN_TIME,
    MARKET_CLOSE_TIME,
)


class TestIsBistBusinessDay:
    """Tests for is_bist_business_day function."""

    def test_monday_is_business_day(self):
        """Monday should be a business day."""
        # April 6, 2026 is Monday
        assert is_bist_business_day(date(2026, 4, 6)) is True

    def test_friday_is_business_day(self):
        """Friday should be a business day."""
        # April 10, 2026 is Friday
        assert is_bist_business_day(date(2026, 4, 10)) is True

    def test_saturday_is_not_business_day(self):
        """Saturday should not be a business day."""
        # April 11, 2026 is Saturday
        assert is_bist_business_day(date(2026, 4, 11)) is False

    def test_sunday_is_not_business_day(self):
        """Sunday should not be a business day."""
        # April 12, 2026 is Sunday
        assert is_bist_business_day(date(2026, 4, 12)) is False

    def test_new_year_is_not_business_day(self):
        """New Year's Day should not be a business day."""
        assert is_bist_business_day(date(2026, 1, 1)) is False

    def test_republic_day_is_not_business_day(self):
        """Republic Day should not be a business day."""
        assert is_bist_business_day(date(2026, 10, 29)) is False

    def test_accepts_datetime(self):
        """Should accept datetime and extract date portion."""
        dt = datetime(2026, 4, 6, 14, 30, tzinfo=ISTANBUL_TZ)
        assert is_bist_business_day(dt) is True


class TestIsBistTradingHours:
    """Tests for is_bist_trading_hours function."""

    def test_during_trading_hours_is_true(self):
        """During market hours should return True."""
        # Monday April 6, 2026 at 11:00 Istanbul time (09:00 UTC)
        dt = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
        assert is_bist_trading_hours(dt) is True

    def test_before_trading_hours_is_false(self):
        """Before market open should return False."""
        # Monday April 6, 2026 at 08:00 Istanbul time (06:00 UTC)
        dt = datetime(2026, 4, 6, 6, 0, tzinfo=timezone.utc)
        assert is_bist_trading_hours(dt) is False

    def test_after_trading_hours_is_false(self):
        """After market close should return False."""
        # Monday April 6, 2026 at 19:00 Istanbul time (17:00 UTC)
        dt = datetime(2026, 4, 6, 17, 0, tzinfo=timezone.utc)
        assert is_bist_trading_hours(dt) is False

    def test_weekend_is_false(self):
        """Weekend should return False regardless of time."""
        # Saturday April 11, 2026 at 12:00 Istanbul time (10:00 UTC)
        dt = datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc)
        assert is_bist_trading_hours(dt) is False

    def test_holiday_is_false(self):
        """Holiday should return False regardless of time."""
        # New Year's Day 2026 at 12:00 Istanbul time
        dt = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        assert is_bist_trading_hours(dt) is False

    def test_market_open_time_is_included(self):
        """Exactly at market open should return True."""
        # Monday at 10:00 Istanbul (08:00 UTC)
        dt = datetime(2026, 4, 6, 8, 0, tzinfo=timezone.utc)
        assert is_bist_trading_hours(dt) is True

    def test_market_close_time_is_excluded(self):
        """Exactly at market close should return False (exclusive)."""
        # Monday at 18:00 Istanbul (16:00 UTC)
        dt = datetime(2026, 4, 6, 16, 0, tzinfo=timezone.utc)
        assert is_bist_trading_hours(dt) is False

    def test_naive_datetime_assumed_utc(self):
        """Naive datetime should be assumed UTC."""
        # 09:00 naive = 12:00 Istanbul = during market hours
        dt = datetime(2026, 4, 6, 9, 0)  # No timezone
        assert is_bist_trading_hours(dt) is True


class TestGetNextTradingDay:
    """Tests for get_next_trading_day function."""

    def test_next_day_from_monday(self):
        """Next trading day from Monday should be Tuesday."""
        result = get_next_trading_day(date(2026, 4, 6))
        assert result == date(2026, 4, 7)

    def test_skips_weekend(self):
        """Next trading day from Friday should be Monday."""
        result = get_next_trading_day(date(2026, 4, 10))
        assert result == date(2026, 4, 13)  # Monday

    def test_next_day_from_sunday(self):
        """Next trading day from Sunday should be Monday."""
        result = get_next_trading_day(date(2026, 4, 12))
        assert result == date(2026, 4, 13)

    def test_accepts_datetime(self):
        """Should accept datetime and extract date portion."""
        dt = datetime(2026, 4, 10, 14, 30)
        result = get_next_trading_day(dt)
        assert result == date(2026, 4, 13)


class TestGetMarketStatus:
    """Tests for get_market_status function."""

    def test_during_trading_hours(self):
        """Should return correct status during trading hours."""
        # Monday at 11:00 Istanbul (09:00 UTC)
        dt = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)
        status = get_market_status(dt)

        assert status["is_open"] is True
        assert status["is_business_day"] is True
        assert status["timezone"] == "Europe/Istanbul"

    def test_after_trading_hours(self):
        """Should return correct status after trading hours."""
        # Monday at 19:00 Istanbul (17:00 UTC)
        dt = datetime(2026, 4, 6, 17, 0, tzinfo=timezone.utc)
        status = get_market_status(dt)

        assert status["is_open"] is False
        assert status["is_business_day"] is True

    def test_weekend(self):
        """Should return correct status on weekend."""
        # Saturday at 12:00 Istanbul (10:00 UTC)
        dt = datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc)
        status = get_market_status(dt)

        assert status["is_open"] is False
        assert status["is_business_day"] is False