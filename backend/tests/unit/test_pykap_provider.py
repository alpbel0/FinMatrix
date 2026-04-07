from datetime import date, datetime

from app.services.data.providers.pykap_provider import PykapProvider


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
