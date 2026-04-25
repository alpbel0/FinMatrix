"""Generate golden files from real PDF fixtures.

Run this script manually whenever parser logic changes:
    cd backend && python tests/fixtures/generate_golden.py

It parses each PDF under tests/fixtures/*.pdf and writes the
extracted elements to tests/fixtures/golden/<pdf_name>.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.pipeline.document_parser import get_structured_pdf_parser


def generate_golden() -> None:
    fixture_dir = Path(__file__).parent
    pdf_files = sorted(fixture_dir.glob("*.pdf"))
    golden_dir = fixture_dir / "golden"
    golden_dir.mkdir(exist_ok=True)

    parser = get_structured_pdf_parser()

    for pdf_path in pdf_files:
        print(f"Parsing {pdf_path.name} ...")
        doc = parser.parse(pdf_path)

        golden_data = {
            "parser_version": doc.parser_version,
            "element_count": len(doc.elements),
            "table_count": len(doc.tables),
            "warnings": doc.warnings,
            "elements": [
                {
                    "element_type": el.element_type,
                    "text": el.text,
                    "markdown": el.markdown,
                    "page_start": el.page_start,
                    "page_end": el.page_end,
                    "section_path": el.section_path,
                    "token_estimate": el.token_estimate,
                    "is_atomic": el.is_atomic,
                    "content_origin": el.content_origin,
                    "has_table_data": el.table_data is not None,
                }
                for el in doc.elements
            ],
            "tables": [
                {
                    "section_path": t.section_path,
                    "markdown_preview": t.markdown[:200] if t.markdown else "",
                    "has_table_data": t.table_data is not None,
                }
                for t in doc.tables
            ],
        }

        golden_path = golden_dir / f"{pdf_path.stem}.json"
        golden_path.write_text(json.dumps(golden_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> Wrote {golden_path.name}")


if __name__ == "__main__":
    generate_golden()
