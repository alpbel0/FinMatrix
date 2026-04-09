"""Enum definitions for type-safe schemas.

This module contains enums used across the application for
consistent vocabulary and type safety.

Key enums:
- DocumentType: KAP filing document types (FR, FAR, ANY)
- QueryIntent: User query intent categories
"""

from enum import Enum


class DocumentType(str, Enum):
    """KAP filing document types.

    Used for filtering retrieval results and query understanding.

    Values:
        FR: Finansal Rapor (Financial Report) - annual, quarterly
        FAR: Faaliyet Raporu (Activity Report)
        ANY: No specific type specified (DEFAULT)
    """

    FR = "FR"  # Finansal Rapor
    FAR = "FAR"  # Faaliyet Raporu
    ANY = "ANY"  # No specific type (DEFAULT)


class QueryIntent(str, Enum):
    """User query intent categories.

    Used by query understanding agent to classify user questions.

    Values:
        SUMMARY: General summary request
        RISK: Risk and threat analysis
        OPPORTUNITY: Opportunity and potential analysis
        METRIC: Specific financial metric query
        GENERIC: Greeting or non-financial question
    """

    SUMMARY = "summary"
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    METRIC = "metric"
    GENERIC = "generic"


class QueryType(str, Enum):
    """High-level chat flow type for CrewAI orchestration."""

    TEXT_ANALYSIS = "text_analysis"
    NUMERICAL_ANALYSIS = "numerical_analysis"
    COMPARISON = "comparison"
    GENERAL = "general"
