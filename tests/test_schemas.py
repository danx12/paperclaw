from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from paperclaw.schemas import (
    ClassifiedDocument,
    DocumentType,
    LibraryDocument,
    RawDocument,
)


def _raw(tmp_path: Path) -> RawDocument:
    return RawDocument(
        source_path=tmp_path / "a.pdf",
        filename="a.pdf",
        size_bytes=0,
        text="",
    )


def test_document_type_is_str_enum():
    assert DocumentType.INVOICE == "invoice"
    assert DocumentType.BANK_STATEMENT == "bank_statement"


def test_raw_document_is_frozen(tmp_path: Path):
    doc = _raw(tmp_path)
    with pytest.raises(ValidationError):
        doc.filename = "b.pdf"  # type: ignore[misc]


def test_classified_confidence_upper_bound(tmp_path: Path):
    with pytest.raises(ValidationError):
        ClassifiedDocument(
            raw=_raw(tmp_path), doc_type=DocumentType.OTHER, confidence=1.5
        )


def test_classified_confidence_lower_bound(tmp_path: Path):
    with pytest.raises(ValidationError):
        ClassifiedDocument(
            raw=_raw(tmp_path), doc_type=DocumentType.OTHER, confidence=-0.1
        )


def test_classified_currency_max_length(tmp_path: Path):
    with pytest.raises(ValidationError):
        ClassifiedDocument(
            raw=_raw(tmp_path),
            doc_type=DocumentType.OTHER,
            confidence=0.5,
            currency="EURO",
        )


def test_classified_accepts_valid_fields(tmp_path: Path):
    doc = ClassifiedDocument(
        raw=_raw(tmp_path),
        doc_type=DocumentType.INVOICE,
        date=datetime.date(2024, 1, 1),
        vendor="Test GmbH",
        amount=42.0,
        currency="EUR",
        reference="REF-1",
        confidence=0.9,
    )
    assert doc.doc_type == "invoice"


def test_library_doc_transcript_must_be_markdown(tmp_path: Path):
    classified = ClassifiedDocument(
        raw=_raw(tmp_path), doc_type=DocumentType.OTHER, confidence=0.5
    )
    with pytest.raises(ValidationError):
        LibraryDocument(
            classified=classified,
            library_path=tmp_path / "a.pdf",
            transcript_path=tmp_path / "a.txt",
            canonical_name="a.pdf",
        )
