"""Mock classes for kap_sdk package testing."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class MockDisclosureBasic:
    """Mock disclosureBasic from kap_sdk."""
    title: str = "Test Disclosure Title"
    mkkMemberOid: str = "test-member-oid"
    companyTitle: str = "Test Company"
    stockCode: str = "THYAO"
    relatedStocks: str | None = None
    disclosureClass: str = "FR"
    disclosureType: str = "Finansal Rapor"
    disclosureCategory: str = "Finansal"
    publishDate: str = "08.04.2026 14:30:00"
    disclosureId: str = "test-disclosure-id"
    disclosureIndex: int = 12345678
    summary: str = "Test disclosure summary text"
    attachmentCount: int = 2
    year: int | None = 2026
    donem: str | None = None
    period: str = "2026"
    hasMultiLanguageSupport: str = "N"
    fundType: str | None = None
    isLate: bool = False
    relatedDisclosureOid: str | None = None
    senderType: str | None = None
    isChanged: bool | None = False
    isBlocked: bool = False


@dataclass
class MockDisclosureDetail:
    """Mock disclosureDetail from kap_sdk."""
    summary: str = "Detailed summary text from disclosure detail"
    content: str | None = None


@dataclass
class MockDisclosure:
    """Mock Disclosure from kap_sdk (contains basic + detail)."""
    disclosureBasic: MockDisclosureBasic = field(default_factory=MockDisclosureBasic)
    disclosureDetail: MockDisclosureDetail | None = None

    def __post_init__(self):
        if self.disclosureDetail is None:
            self.disclosureDetail = MockDisclosureDetail()


@dataclass
class MockCompany:
    """Mock Company from kap_sdk."""
    path: str = "test-company-path"
    name: str = "Turk Hava Yollari AO"
    code: str = "THYAO"
    city: str = "Istanbul"
    independent_audit_firm: str = "Test Auditor"


@dataclass
class MockCompanyInfo:
    """Mock CompanyInfo from kap_sdk."""
    address: str = "Test Address, Istanbul"
    mail: list[str] = field(default_factory=lambda: ["test@thy.com"])
    website: str = "https://www.turkishairlines.com"
    companys_duration: str = "50+ years"
    independent_audit_firm: str = "Test Auditor"
    indices: list[str] = field(default_factory=lambda: ["BIST 30", "BIST 100"])
    sectors: list[str] = field(default_factory=lambda: ["Ulastirma"])
    equity_market: str = "Yildiz Pazar"


class MockAnnouncementType:
    """Mock AnnouncementType enum-like class from kap_sdk."""
    MaterialEventDisclosure = "ODA"
    FinancialStatement = "FR"
    RegulatoryAuthorityAnnouncements = "DUY"
    Other = "DG"
    Corporate_Actions = "CA"


class MockMemberType:
    """Mock MemberType enum-like class from kap_sdk."""
    BistCompanies = "IGS"
    InvestmentFirms = "YK"
    PortfolioManagementCompanies = "PYS"
    RegulatoryAuthorities = "DDK"
    OtherKAPMembers = "DG"


class MockKapClient:
    """Mock KapClient from kap_sdk for testing."""

    def __init__(
        self,
        cache_expiry: int = 3600,
        company_cache_expiry: int = 86400,
        indices_cache_expiry: int = 86400,
        sectors_cache_expiry: int = 86400,
    ):
        self.cache_expiry = cache_expiry
        self.company_cache_expiry = company_cache_expiry
        self._companies = self._create_default_companies()

    def _create_default_companies(self) -> list[MockCompany]:
        """Create default mock companies."""
        return [
            MockCompany(code="THYAO", name="Turk Hava Yollari AO", city="Istanbul"),
            MockCompany(code="GARAN", name="Garanti Bankasi AS", city="Istanbul"),
            MockCompany(code="ASELS", name="Aselsan AS", city="Ankara"),
        ]

    async def get_companies(self) -> list[MockCompany]:
        """Get all mock companies."""
        return self._companies

    async def get_company(self, code: str) -> MockCompany | None:
        """Get specific company by code."""
        for company in self._companies:
            if company.code == code.upper():
                return company
        return None

    async def get_announcements(
        self,
        company: MockCompany | None = None,
        fromdate: date | None = None,
        todate: date | None = None,
        disclosure_type: list[Any] | None = None,
        fund_types: list[Any] | None = None,
        member_types: list[Any] | None = None,
    ) -> list[MockDisclosure]:
        """Get mock announcements."""
        # Return mock disclosures for testing
        disclosures = [
            MockDisclosure(
                disclosureBasic=MockDisclosureBasic(
                    disclosureIndex=12345678,
                    stockCode=company.code if company else "THYAO",
                    title=f"{company.name if company else 'Test'} - Finansal Rapor 2026" if company else "Test Disclosure",
                    disclosureClass="FR",
                    publishDate="08.04.2026 14:30:00",
                    summary="Financial report summary",
                    attachmentCount=2,
                    isLate=False,
                ),
                disclosureDetail=MockDisclosureDetail(
                    summary="Detailed financial report summary"
                ),
            ),
            MockDisclosure(
                disclosureBasic=MockDisclosureBasic(
                    disclosureIndex=12345679,
                    stockCode=company.code if company else "THYAO",
                    title=f"{company.name if company else 'Test'} - Olaylara Duyarlilik" if company else "Material Event",
                    disclosureClass="ODA",
                    publishDate="07.04.2026 10:00:00",
                    summary="Material event disclosure",
                    attachmentCount=1,
                    isLate=False,
                ),
                disclosureDetail=MockDisclosureDetail(
                    summary="Material event summary"
                ),
            ),
        ]
        return disclosures

    async def get_company_info(
        self,
        company: MockCompany,
        fetch_remote: bool = False,
    ) -> MockCompanyInfo | None:
        """Get mock company info."""
        return MockCompanyInfo()

    async def get_financial_report(
        self,
        company: MockCompany,
        year: str = "2023",
        fetch_remote: bool = False,
    ) -> dict[str, Any]:
        """Get mock financial report."""
        return {
            "year": year,
            "revenue": 100000000,
            "net_income": 50000000,
        }

    async def get_indices(self, fetch_remote: bool = False) -> list[Any]:
        """Get mock indices."""
        return []

    async def get_sectors(self, fetch_remote: bool = False) -> list[Any]:
        """Get mock sectors."""
        return []

    def clear_cache(self) -> None:
        """Clear mock cache."""
        pass


def create_mock_disclosure(
    disclosure_index: int,
    symbol: str = "THYAO",
    title: str = "Test Disclosure",
    filing_type: str = "FR",
    publish_date: str = "08.04.2026 14:30:00",
    summary: str = "Test summary",
    attachment_count: int = 1,
    is_late: bool = False,
) -> MockDisclosure:
    """Factory function to create mock disclosure with custom values."""
    return MockDisclosure(
        disclosureBasic=MockDisclosureBasic(
            disclosureIndex=disclosure_index,
            stockCode=symbol,
            title=title,
            disclosureClass=filing_type,
            publishDate=publish_date,
            summary=summary,
            attachmentCount=attachment_count,
            isLate=is_late,
        ),
        disclosureDetail=MockDisclosureDetail(summary=summary),
    )