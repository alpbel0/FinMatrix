"""Mock fixtures for FinMatrix testing.

Provides mock implementations for:
- KAP providers (borsapy, pykap, kap_sdk)
- Provider-agnostic KAP fixtures (mock_kap)
- ChromaDB embedding storage (mock_chromadb)

Usage:
    from tests.mocks import MockTicker, MockBISTCompany, MockChromaClient
    from tests.mocks import create_financial_report_filing, create_mock_collection_with_documents
"""

# Existing provider mocks
from tests.mocks.mock_borsapy import (
    MockTicker,
    MockTickers,
    MockFastInfo,
    MockIsYatirim,
    create_mock_price_dataframe,
    create_mock_news_dataframe,
    create_mock_financial_dataframe,
    create_ticker_that_raises,
)

from tests.mocks.mock_pykap import (
    MockBISTCompany,
    mock_get_general_info,
    create_mock_disclosure_dict,
    create_mock_general_info_dict,
    create_company_that_raises,
    MockPykapModule,
)

from tests.mocks.mock_kap_sdk import (
    MockDisclosureBasic,
    MockDisclosureDetail,
    MockDisclosure,
    MockCompany,
    MockCompanyInfo,
    MockKapClient,
    MockAnnouncementType,
    MockMemberType,
    create_mock_disclosure,
)

# Provider-agnostic KAP fixtures (Task 4.5)
from tests.mocks.mock_kap import (
    create_standard_kap_filing,
    create_financial_report_filing,
    create_material_event_filing,
    create_activity_report_filing,
    create_late_disclosure_filing,
    create_multi_attachment_filing,
    create_kap_filings_batch_for_scheduler,
    create_kap_filings_for_single_symbol,
    create_kap_filing_with_missing_fields,
    create_kap_filing_with_related_stocks,
    create_empty_kap_filing_list,
    create_filing_with_invalid_disclosure_index,
    create_kap_filing_dict_for_mapper,
)

# ChromaDB mock for Week 5 (Task 4.5)
from tests.mocks.mock_chromadb import (
    MockChromaClient,
    MockChromaCollection,
    MockChromaDocument,
    MockQueryResult,
    create_mock_embedding,
    create_mock_chroma_client,
    create_mock_collection_with_documents,
    DEFAULT_EMBEDDING_DIMENSION,
)

__all__ = [
    # borsapy mocks
    "MockTicker",
    "MockTickers",
    "MockFastInfo",
    "MockIsYatirim",
    "create_mock_price_dataframe",
    "create_mock_news_dataframe",
    "create_mock_financial_dataframe",
    "create_ticker_that_raises",
    # pykap mocks
    "MockBISTCompany",
    "mock_get_general_info",
    "create_mock_disclosure_dict",
    "create_mock_general_info_dict",
    "create_company_that_raises",
    "MockPykapModule",
    # kap_sdk mocks
    "MockDisclosureBasic",
    "MockDisclosureDetail",
    "MockDisclosure",
    "MockCompany",
    "MockCompanyInfo",
    "MockKapClient",
    "MockAnnouncementType",
    "MockMemberType",
    "create_mock_disclosure",
    # mock_kap (Task 4.5)
    "create_standard_kap_filing",
    "create_financial_report_filing",
    "create_material_event_filing",
    "create_activity_report_filing",
    "create_late_disclosure_filing",
    "create_multi_attachment_filing",
    "create_kap_filings_batch_for_scheduler",
    "create_kap_filings_for_single_symbol",
    "create_kap_filing_with_missing_fields",
    "create_kap_filing_with_related_stocks",
    "create_empty_kap_filing_list",
    "create_filing_with_invalid_disclosure_index",
    "create_kap_filing_dict_for_mapper",
    # mock_chromadb (Task 4.5)
    "MockChromaClient",
    "MockChromaCollection",
    "MockChromaDocument",
    "MockQueryResult",
    "create_mock_embedding",
    "create_mock_chroma_client",
    "create_mock_collection_with_documents",
    "DEFAULT_EMBEDDING_DIMENSION",
]