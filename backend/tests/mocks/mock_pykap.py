"""Mock classes for pykap package testing.

Provides mock implementations of pykap.BISTCompany and get_general_info
for unit testing without real KAP API calls.

Key features:
- Disclosure list generation
- Date filtering simulation
- Error injection capabilities
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock


# KAP disclosure subject UUIDs (matching pykap constants)
KAP_SUBJECT_FINANCIAL_REPORT = "4028328c594bfdca01594c0af9aa0057"
KAP_SUBJECT_OPERATING_REPORT = "4028328d594c04f201594c5155dd0076"

# Valid disclosure types
VALID_DISCLOSURE_TYPES = {"FAR", "KYUR", "SUR", "KDP", "DEG", "UNV", "SYI", "FR"}


@dataclass
class MockBISTCompany:
    """Mock pykap.BISTCompany for unit testing."""

    symbol: str
    disclosures: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    historical_disclosures: list[dict[str, Any]] = field(default_factory=list)
    raise_on_create: bool = False
    raise_on_get_disclosures: str | None = None  # Disclosure type to raise error on
    raise_on_historical: bool = False

    def __post_init__(self):
        if self.raise_on_create:
            raise ValueError(f"Invalid symbol: {self.symbol}")

        # Initialize with default disclosures if empty
        if not self.disclosures:
            self.disclosures = self._default_disclosures()

        if not self.historical_disclosures:
            self.historical_disclosures = self._default_historical_disclosures()

    def _default_disclosures(self) -> dict[str, list[dict[str, Any]]]:
        """Generate default mock disclosures for common types."""
        now = datetime.now()
        date_str = now.strftime("%d.%m.%Y %H:%M:%S")

        return {
            "FAR": [
                {
                    "disclosureIndex": 12345678,
                    "title": f"{self.symbol} Faaliyet Raporu 2025",
                    "publishDate": date_str,
                    "disclosureClass": "FAR",
                    "year": 2025,
                    "period": "2025",
                },
            ],
            "ODA": [
                {
                    "disclosureIndex": 12345679,
                    "title": f"{self.symbol} Olaylara Duyarlilik Bildirimi",
                    "publishDate": (now - timedelta(days=1)).strftime("%d.%m.%Y %H:%M:%S"),
                    "disclosureClass": "ODA",
                },
            ],
        }

    def _default_historical_disclosures(self) -> list[dict[str, Any]]:
        """Generate default mock historical FR disclosures."""
        now = datetime.now()
        return [
            {
                "disclosureIndex": 11111111,
                "title": f"{self.symbol} Finansal Rapor",
                "disclosureClass": "FR",
                "year": 2024,
                "ruleType": "2024",
                "ruleTypeTerm": "2024",
            },
            {
                "disclosureIndex": 11111112,
                "title": f"{self.symbol} Finansal Rapor Q3",
                "disclosureClass": "FR",
                "year": 2024,
                "ruleType": "Q3",
                "ruleTypeTerm": "2024 Q3",
            },
        ]

    def get_historical_disclosure_list(
        self,
        fromdate: date | None = None,
        todate: date | None = None,
        disclosure_type: str = "FR",
        subject: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return mock historical disclosure list.

        Args:
            fromdate: Filter disclosures after this date
            todate: Filter disclosures before this date
            disclosure_type: Type of disclosure (FR for financial reports)
            subject: KAP subject UUID

        Returns:
            List of disclosure dicts with disclosureIndex, year, ruleType, etc.
        """
        if self.raise_on_historical:
            raise ConnectionError("KAP API connection failed")

        # Simulate date filtering - in real pykap, this would filter server-side
        disclosures = self.historical_disclosures

        # Add publish dates for filtering simulation
        result = []
        for disc in disclosures:
            # Add approximate publish date based on year/quarter
            year = disc.get("year")
            rule_type = disc.get("ruleTypeTerm", "")
            if year:
                if "Q" in rule_type:
                    quarter = int(rule_type.split("Q")[-1])
                    month = quarter * 3
                else:
                    month = 12
                disc["publishDate"] = datetime(year, month, 28, 14, 30).strftime("%d.%m.%Y %H:%M:%S")

            # Filter by date if specified
            pub_date = datetime.strptime(disc.get("publishDate", "01.01.2025 00:00:00"), "%d.%m.%Y %H:%M:%S")
            if fromdate and pub_date.date() < fromdate:
                continue
            if todate and pub_date.date() > todate:
                continue

            result.append(disc)

        return result

    def get_disclosures(self, disclosure_type: str) -> list[dict[str, Any]]:
        """Return mock disclosures for a specific type.

        Args:
            disclosure_type: Disclosure type code (FAR, ODA, etc.)

        Returns:
            List of disclosure dicts
        """
        if self.raise_on_get_disclosures == disclosure_type:
            raise TimeoutError(f"Timeout fetching {disclosure_type} disclosures")

        return self.disclosures.get(disclosure_type, [])


def mock_get_general_info(symbol: str) -> dict[str, Any] | None:
    """Mock implementation of pykap's get_general_info function.

    Args:
        symbol: BIST stock symbol

    Returns:
        Dict with 'name' and 'summary_page' keys, or None for invalid symbols
    """
    # Simulate valid symbols
    valid_symbols = {"THYAO", "GARAN", "ASELS", "SAHOL", "AKBNK"}

    if symbol.upper() not in valid_symbols:
        return None

    return {
        "name": f"{symbol.upper()} Company Name",
        "summary_page": f"https://www.kap.org.tr/tr/sirket-bilgileri/{symbol.upper()}",
    }


def create_mock_disclosure_dict(
    disclosure_index: int,
    title: str = "Test Disclosure",
    disclosure_class: str = "FR",
    publish_date: str | None = None,
    year: int | None = None,
    rule_type: str | None = None,
    rule_type_term: str | None = None,
) -> dict[str, Any]:
    """
    Create a mock disclosure dict matching pykap's disclosureBasic format.

    Args:
        disclosure_index: Unique disclosure ID
        title: Disclosure title
        disclosure_class: Disclosure type (FR, FAR, ODA, etc.)
        publish_date: Date string in KAP format (DD.MM.YYYY HH:MM:SS)
        year: Year of report
        rule_type: Rule type (e.g., "2024", "Q3")
        rule_type_term: Full rule type term (e.g., "2024 Q3")

    Returns:
        Dict with pykap disclosureBasic fields
    """
    if publish_date is None:
        publish_date = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    return {
        "disclosureIndex": disclosure_index,
        "title": title,
        "disclosureClass": disclosure_class,
        "publishDate": publish_date,
        "year": year,
        "ruleType": rule_type,
        "ruleTypeTerm": rule_type_term,
        "period": f"{year}" if year else None,
    }


def create_mock_general_info_dict(
    symbol: str,
    name: str | None = None,
    summary_page: str | None = None,
) -> dict[str, Any]:
    """
    Create a mock general info dict matching pykap's get_general_info format.

    Args:
        symbol: Stock symbol
        name: Company name (defaults to symbol + " Company")
        summary_page: KAP summary page URL

    Returns:
        Dict with 'name' and 'summary_page' keys
    """
    return {
        "name": name or f"{symbol} Company",
        "summary_page": summary_page or f"https://www.kap.org.tr/tr/sirket-bilgileri/{symbol}",
    }


# Error injection helpers

def create_company_that_raises(symbol: str, error_type: str = "create") -> MockBISTCompany:
    """
    Create a MockBISTCompany configured to raise specific errors.

    Args:
        symbol: Stock symbol
        error_type: "create", "historical", or a disclosure type like "FAR"

    Returns:
        MockBISTCompany configured to raise the specified error
    """
    if error_type == "create":
        # Will raise ValueError on construction
        return MockBISTCompany(symbol=symbol, raise_on_create=True)

    company = MockBISTCompany(symbol=symbol)

    if error_type == "historical":
        company.raise_on_historical = True
    else:
        # Treat as disclosure type
        company.raise_on_get_disclosures = error_type

    return company


class MockPykapModule:
    """Mock the entire pykap module structure for patching."""

    class BISTCompany(MockBISTCompany):
        """Alias for MockBISTCompany for module patching."""
        pass

    @staticmethod
    def get_general_info(symbol: str) -> dict[str, Any] | None:
        """Alias for mock_get_general_info for module patching."""
        return mock_get_general_info(symbol)