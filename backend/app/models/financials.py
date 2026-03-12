"""
Shared ENUM definitions for financial statements and data sync.

This module contains:
- PeriodType: Financial statement period type (Q1, Q2, Q3, Q4, ANNUAL)
- SyncStatus: Sync status for KAP reports and embeddings
- NewsSource: News source type
"""

from enum import Enum as PyEnum


class PeriodType(str, PyEnum):
    """Financial statement period type."""

    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    ANNUAL = "ANNUAL"


class SyncStatus(str, PyEnum):
    """Sync status for KAP reports and embeddings."""

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class NewsSource(str, PyEnum):
    """News source type."""

    KAP_SUMMARY = "kap_summary"
    EXTERNAL_NEWS = "external_news"
    MANUAL = "manual"