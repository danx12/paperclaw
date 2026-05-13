from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperclaw._tools import TOOL_SCHEMAS, execute_tool
from paperclaw.library_index import LibraryIndex

SIDECAR_A = """\
# 2024-01-15_invoice_acme_INV-1.pdf

**Type**: invoice
**Date**: 2024-01-15
**Vendor**: Acme
**Amount**: 100.0 EUR
**Reference**: INV-1
**Confidence**: 90%

## Extracted Text

Acme invoice for widgets.
Total: 100.00 EUR
"""

SIDECAR_B = """\
# 2024-06-10_bill_stadtwerke_R-22.pdf

**Type**: bill
**Date**: 2024-06-10
**Vendor**: Stadtwerke München
**Reference**: R-22
**Confidence**: 88%

## Extracted Text

Stromrechnung Juni 2024
Kundennummer 99999
"""


@pytest.fixture
def index(tmp_path: Path) -> LibraryIndex:
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "2024-01-15_invoice_acme_INV-1.md").write_text(SIDECAR_A, encoding="utf-8")
    (lib / "2024-06-10_bill_stadtwerke_R-22.md").write_text(SIDECAR_B, encoding="utf-8")
    return LibraryIndex.load(lib)


def test_tool_schemas_have_required_fields() -> None:
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert names == {
        "list_documents",
        "search_documents",
        "read_document",
        "grep_documents",
    }
    for tool in TOOL_SCHEMAS:
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


def test_list_documents_paginates(index: LibraryIndex) -> None:
    out = json.loads(execute_tool("list_documents", {"page": 1, "page_size": 1}, index))
    assert out["page"] == 1
    assert out["page_size"] == 1
    assert out["total_results"] == 2
    assert out["total_pages"] == 2
    assert out["has_more"] is True
    assert len(out["results"]) == 1


def test_list_documents_sorts_date_desc_by_default(index: LibraryIndex) -> None:
    out = json.loads(execute_tool("list_documents", {}, index))
    dates = [r["date"] for r in out["results"]]
    assert dates == sorted(dates, reverse=True)


def test_search_filters_by_type(index: LibraryIndex) -> None:
    out = json.loads(execute_tool("search_documents", {"doc_type": "bill"}, index))
    assert out["total_results"] == 1
    assert out["results"][0]["canonical_name"].startswith("2024-06-10_bill")


def test_search_filters_by_date_range(index: LibraryIndex) -> None:
    out = json.loads(
        execute_tool(
            "search_documents",
            {"date_from": "2024-05-01", "date_to": "2024-12-31"},
            index,
        )
    )
    assert out["total_results"] == 1


def test_read_document_returns_full_text(index: LibraryIndex) -> None:
    out = json.loads(
        execute_tool(
            "read_document",
            {"name": "2024-01-15_invoice_acme_INV-1.pdf"},
            index,
        )
    )
    assert "widgets" in out["extracted_text"]
    assert out["vendor"] == "Acme"
    assert out["text_truncated"] is False


def test_read_document_truncates_when_requested(index: LibraryIndex) -> None:
    out = json.loads(
        execute_tool(
            "read_document",
            {"name": "2024-01-15_invoice_acme_INV-1.pdf", "max_chars": 10},
            index,
        )
    )
    assert out["text_truncated"] is True
    assert len(out["extracted_text"]) == 10


def test_read_document_missing_name_returns_error(index: LibraryIndex) -> None:
    out = json.loads(
        execute_tool("read_document", {"name": "does-not-exist.pdf"}, index)
    )
    assert "error" in out


def test_grep_finds_match(index: LibraryIndex) -> None:
    out = json.loads(
        execute_tool("grep_documents", {"pattern": r"Kundennummer \d+"}, index)
    )
    assert out["match_count"] == 1
    assert out["matches"][0]["document"].startswith("2024-06-10_bill")


def test_grep_invalid_regex_returns_error(index: LibraryIndex) -> None:
    out = json.loads(execute_tool("grep_documents", {"pattern": "[unclosed"}, index))
    assert "error" in out


def test_unknown_tool_returns_error(index: LibraryIndex) -> None:
    out = json.loads(execute_tool("nope", {}, index))
    assert "error" in out
