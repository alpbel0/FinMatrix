from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.services.data.providers.pykap_provider import (
    EXTENDED_DISCLOSURE_TYPES,
    FinMatrixBISTCompany,
    KAP_SUBJECT_FINANCIAL_REPORT,
    PykapProvider,
    _normalize_related_stocks,
)


def test_parse_publish_date_supports_kap_datetime_format():
    provider = PykapProvider()

    parsed = provider._parse_publish_date("04.03.2026 21:18:52")

    assert parsed == datetime(2026, 3, 4, 21, 18, 52)


def test_extract_disclosure_datetime_checks_fallback_fields():
    provider = PykapProvider()

    parsed = provider._extract_disclosure_datetime(
        {
            "publishDate": None,
            "updateDate": "2026-03-04T21:18:52",
        }
    )

    assert parsed == datetime(2026, 3, 4, 21, 18, 52)


def test_map_disclosure_basic_to_filing_uses_resolved_datetime():
    provider = PykapProvider()

    filing = provider._map_disclosure_basic_to_filing(
        {
            "disclosureIndex": 12345,
            "title": "Faaliyet Raporu",
            "publishDate": "04.03.2026 21:18:52",
        },
        "THYAO",
        "FAR",
    )

    assert filing is not None
    assert filing.published_at == datetime(2026, 3, 4, 21, 18, 52)
    assert filing.pdf_url == "https://www.kap.org.tr/tr/api/BildirimPdf/12345"


def test_filtered_disclosure_loop_skips_undated_records():
    provider = PykapProvider()
    start_date = date(2026, 3, 1)
    disclosures = [
        {
            "disclosureIndex": 1,
            "title": "Undated filing",
            "publishDate": None,
        },
        {
            "disclosureIndex": 2,
            "title": "Recent filing",
            "publishDate": "04.03.2026 21:18:52",
        },
    ]

    filings = []
    for disclosure in disclosures:
        published_at = provider._extract_disclosure_datetime(disclosure)
        if published_at is None:
            continue
        if published_at.date() < start_date:
            continue
        filing = provider._map_disclosure_basic_to_filing(
            disclosure,
            "THYAO",
            "FAR",
            published_at=published_at,
        )
        if filing is not None:
            filings.append(filing)

    assert len(filings) == 1
    assert filings[0].title == "Recent filing"


def test_finmatrix_company_historical_disclosure_uses_empty_subject_list_for_unknown_subject():
    company = FinMatrixBISTCompany.__new__(FinMatrixBISTCompany)
    company.ticker = "THYAO"
    company.company_id = 123

    response = MagicMock()
    response.text = "[]"
    response.raise_for_status = MagicMock()

    with patch("requests.post", return_value=response) as mock_post:
        result = company.get_historical_disclosure_list(
            fromdate=date(2024, 1, 1),
            todate=date(2024, 1, 31),
            disclosure_type="ODA",
            subject="unknown-subject",
        )

    assert result == []
    assert mock_post.call_args.kwargs["json"]["subjectList"] == []
    assert mock_post.call_args.kwargs["json"]["disclosureClass"] == "ODA"


def test_finmatrix_company_historical_disclosure_preserves_known_uuid():
    company = FinMatrixBISTCompany.__new__(FinMatrixBISTCompany)
    company.ticker = "THYAO"
    company.company_id = 123

    response = MagicMock()
    response.text = "[]"
    response.raise_for_status = MagicMock()

    with patch("requests.post", return_value=response) as mock_post:
        company.get_historical_disclosure_list(subject=KAP_SUBJECT_FINANCIAL_REPORT)

    assert mock_post.call_args.kwargs["json"]["subjectList"] == [KAP_SUBJECT_FINANCIAL_REPORT]


def test_finmatrix_company_get_disclosures_allows_extended_types_without_validation_error():
    company = FinMatrixBISTCompany.__new__(FinMatrixBISTCompany)
    company.ticker = "THYAO"
    company.company_id = 123

    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = [{"disclosureBasic": {"disclosureIndex": 42, "title": "Test"}}]

    with patch("requests.get", return_value=response) as mock_get:
        result = company.get_disclosures("ODA")

    assert result == [{"disclosureIndex": 42, "title": "Test"}]
    assert "/ODA/123" in mock_get.call_args.args[0]


def test_create_company_returns_finmatrix_subclass():
    provider = PykapProvider()

    with patch("app.services.data.providers.pykap_provider.FinMatrixBISTCompany") as mock_company_cls:
        mock_company = MagicMock(spec=FinMatrixBISTCompany)
        mock_company_cls.return_value = mock_company
        company = provider._create_company("thyao")

    assert company is mock_company
    mock_company_cls.assert_called_once_with("THYAO")


def test_get_kap_filings_supports_extended_types():
    provider = PykapProvider()
    company = MagicMock()
    company.get_historical_disclosure_list.side_effect = [
        [{"disclosureIndex": 1, "year": 2024, "ruleType": "Yıllık"}],
        [
            {
                "disclosureIndex": 2,
                "publishDate": "06.03.2026 10:15:00",
                "summary": "Ozel Durum",
                "relatedStocks": "THYAO, ASELS",
            }
        ],
        [
            {
                "disclosureIndex": 4,
                "publishDate": "07.03.2026 09:30:00",
                "subject": "Sirket Genel Bilgi Formu",
            }
        ],
    ]
    company.get_disclosures.return_value = []

    with patch.object(provider, "_create_company", return_value=company):
        filings = provider.get_kap_filings(
            "THYAO",
            start_date=date(2026, 3, 1),
            filing_types=["FR", "ODA", "DG"],
        )

    assert isinstance(filings, list)
    assert {filing.filing_type for filing in filings} == {"FR", "ODA", "DG"}
    assert company.get_disclosures.call_count == 0
    assert company.get_historical_disclosure_list.call_args_list[1].kwargs["subject"] is None
    assert company.get_historical_disclosure_list.call_args_list[2].kwargs["disclosure_type"] == "DG"


def test_map_historical_disclosure_to_filing_uses_summary_and_related_stocks():
    provider = PykapProvider()

    filing = provider._map_historical_disclosure_to_filing(
        {
            "disclosureIndex": 1592906,
            "publishDate": "14.04.2026 11:55:13",
            "summary": "Olagan Genel Kurul Toplanti Kararlarinin Tescili",
            "subject": "Genel Kurul Islemlerine Iliskin Bildirim",
            "attachmentCount": 7,
            "isLate": False,
            "relatedStocks": "THYAO, ASELS , THYAO",
        },
        "THYAO",
        "ODA",
    )

    assert filing is not None
    assert filing.title == "Olagan Genel Kurul Toplanti Kararlarinin Tescili"
    assert filing.published_at == datetime(2026, 4, 14, 11, 55, 13)
    assert filing.attachment_count == 7
    assert filing.is_late is False
    assert filing.related_stocks == ["THYAO", "ASELS"]


def test_map_historical_disclosure_to_filing_falls_back_to_subject_for_title():
    provider = PykapProvider()

    filing = provider._map_historical_disclosure_to_filing(
        {
            "disclosureIndex": 1590424,
            "publishDate": "09.04.2026 21:56:21",
            "subject": "Sirket Genel Bilgi Formu",
        },
        "THYAO",
        "DG",
    )

    assert filing is not None
    assert filing.title == "Sirket Genel Bilgi Formu"
    assert filing.published_at == datetime(2026, 4, 9, 21, 56, 21)


def test_normalize_related_stocks_handles_string_and_list_inputs():
    assert _normalize_related_stocks("THYAO, ASELS , THYAO") == ["THYAO", "ASELS"]
    assert _normalize_related_stocks(["THYAO, ASELS", " KCHOL ", None]) == ["THYAO", "ASELS", "KCHOL"]
    assert _normalize_related_stocks(None) is None


def test_extended_disclosure_types_include_new_kap_classes():
    assert {"FR", "ODA", "DG", "DKB"}.issubset(EXTENDED_DISCLOSURE_TYPES)
