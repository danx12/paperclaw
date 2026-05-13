from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from paperclaw.library_index import LibraryEntry, LibraryIndex, render_metadata_table

SIDECAR_INVOICE = """\
# 2024-11-01_invoice_acme-gmbh_INV-9912.pdf

**Source**: acme.pdf
**Extracted**: 2024-11-02T09:14:33Z
**PaperClaw**: 0.1.0
**Type**: invoice
**Date**: 2024-11-01
**Vendor**: Acme GmbH
**Amount**: 99.0 EUR
**Reference**: INV-9912
**Confidence**: 90%

## Extracted Text

Acme GmbH
Invoice INV-9912
Total: 99.00 EUR
"""

SIDECAR_BILL = """\
# 2024-12-15_bill_stadtwerke_R-118442.pdf

**Source**: bill.pdf
**Extracted**: 2024-12-16T09:14:33Z
**PaperClaw**: 0.1.0
**Type**: bill
**Date**: 2024-12-15
**Vendor**: Stadtwerke München
**Reference**: R-118442
**Confidence**: 88%

## Extracted Text

Stadtwerke München
Stromrechnung
Verbrauch: 1234 kWh
"""

SIDECAR_UNKNOWN = """\
# 0000-00-00_other_unknown_noref.pdf

**Source**: mystery.pdf
**Extracted**: 2025-01-01T09:14:33Z
**PaperClaw**: 0.1.0
**Type**: other
**Date**: unknown
**Vendor**: unknown
**Confidence**: 30%

## Extracted Text

unclassifiable
"""


@pytest.fixture
def library(tmp_path: Path) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "2024-11-01_invoice_acme-gmbh_INV-9912.md").write_text(
        SIDECAR_INVOICE, encoding="utf-8"
    )
    (lib / "2024-12-15_bill_stadtwerke_R-118442.md").write_text(
        SIDECAR_BILL, encoding="utf-8"
    )
    unsorted = lib / "_unsorted"
    unsorted.mkdir()
    (unsorted / "mystery_abcd1234.md").write_text(SIDECAR_UNKNOWN, encoding="utf-8")
    return lib


def test_load_parses_all_sidecars(library: Path) -> None:
    idx = LibraryIndex.load(library)
    assert len(idx) == 3
    names = {e.canonical_name for e in idx}
    assert "2024-11-01_invoice_acme-gmbh_INV-9912.pdf" in names
    assert "0000-00-00_other_unknown_noref.pdf" in names


def test_field_parsing(library: Path) -> None:
    idx = LibraryIndex.load(library)
    invoice = idx.get("2024-11-01_invoice_acme-gmbh_INV-9912.pdf")
    assert invoice is not None
    assert invoice.doc_type == "invoice"
    assert invoice.date == datetime.date(2024, 11, 1)
    assert invoice.vendor == "Acme GmbH"
    assert invoice.amount == "99.0 EUR"
    assert invoice.reference == "INV-9912"
    assert invoice.confidence == 90
    assert "Acme GmbH" in invoice.text
    assert invoice.unsorted is False


def test_unsorted_flag(library: Path) -> None:
    idx = LibraryIndex.load(library)
    mystery = idx.get("0000-00-00_other_unknown_noref.pdf")
    assert mystery is not None
    assert mystery.unsorted is True
    assert mystery.vendor is None
    assert mystery.date is None


def test_filter_by_type(library: Path) -> None:
    idx = LibraryIndex.load(library)
    bills = idx.filter(doc_type="bill")
    assert [e.canonical_name for e in bills] == [
        "2024-12-15_bill_stadtwerke_R-118442.pdf"
    ]


def test_filter_by_vendor_case_insensitive(library: Path) -> None:
    idx = LibraryIndex.load(library)
    hits = idx.filter(vendor="acme")
    assert len(hits) == 1


def test_filter_date_range(library: Path) -> None:
    idx = LibraryIndex.load(library)
    hits = idx.filter(date_from=datetime.date(2024, 12, 1))
    assert [e.doc_type for e in hits] == ["bill"]


def test_filter_text_searches_body(library: Path) -> None:
    idx = LibraryIndex.load(library)
    hits = idx.filter(text="verbrauch")
    assert len(hits) == 1
    assert hits[0].doc_type == "bill"


def test_grep_returns_line_numbers(library: Path) -> None:
    idx = LibraryIndex.load(library)
    hits = idx.grep(r"INV-\d+")
    assert len(hits) == 1
    entry, lineno, line = hits[0]
    assert entry.doc_type == "invoice"
    assert lineno >= 1
    assert "INV-9912" in line


def test_grep_invalid_pattern_raises(library: Path) -> None:
    idx = LibraryIndex.load(library)
    with pytest.raises(ValueError):
        idx.grep("[unclosed")


def test_render_metadata_table_contains_all_rows(library: Path) -> None:
    idx = LibraryIndex.load(library)
    table = render_metadata_table(idx)
    lines = table.splitlines()
    assert lines[0].startswith("name | date | type")
    assert len(lines) == 1 + len(idx)


def test_png_canonical_name_from_h1(tmp_path: Path) -> None:
    lib = tmp_path / "library"
    lib.mkdir()
    sidecar = lib / "2025-01-01_letter_someone_noref.md"
    sidecar.write_text(
        "# 2025-01-01_letter_someone_noref.png\n\n"
        "**Type**: letter\n**Date**: 2025-01-01\n**Vendor**: Someone\n"
        "**Confidence**: 80%\n\n## Extracted Text\n\nhello\n",
        encoding="utf-8",
    )
    idx = LibraryIndex.load(lib)
    entry = next(iter(idx))
    assert entry.canonical_name.endswith(".png")
    assert isinstance(entry, LibraryEntry)
