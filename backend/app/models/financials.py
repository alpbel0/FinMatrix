"""
Shared ENUM definitions for financial statements.

This module contains:
- PeriodType: Financial statement period type (Q1, Q2, Q3, Q4, ANNUAL)
"""

from enum import Enum as PyEnum


class PeriodType(str, PyEnum):
    """Financial statement period type."""

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    ANNUAL = "ANNUAL"