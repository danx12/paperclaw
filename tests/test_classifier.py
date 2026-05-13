from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paperclaw.classifier import ClaudeClassifier, LocalRulesClassifier
from paperclaw.schemas import ClassifiedDocument, DocumentType, RawDocument


def _raw(tmp_path: Path, filename: str = "test.pdf", text: str = "") -> RawDocument:
    p = tmp_path / filename
    p.write_bytes(b"stub")
    return RawDocument(source_path=p, filename=filename, size_bytes=4, text=text)


def _mock_response(data: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock()]
    msg.content[0].text = json.dumps(data)
    return msg


class TestLocalRulesClassifier:
    def test_empty_text_confidence_zero(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text=""))
        assert doc.confidence == 0.0
        assert doc.doc_type == DocumentType.OTHER

    def test_whitespace_only_text(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text="   \n  "))
        assert doc.confidence == 0.0

    def test_filename_match_high_confidence(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(
            _raw(tmp_path, filename="rechnung-2024.pdf", text="unrelated")
        )
        assert doc.confidence == 0.85
        assert doc.doc_type == DocumentType.INVOICE

    def test_content_match_medium_confidence(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(
            _raw(tmp_path, filename="doc.pdf", text="invoice for services")
        )
        assert doc.confidence == 0.60
        assert doc.doc_type == DocumentType.INVOICE

    def test_no_match_low_confidence(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, filename="doc.pdf", text="lorem ipsum dolor"))
        assert doc.confidence == 0.30
        assert doc.doc_type == DocumentType.OTHER

    def test_bank_statement_content(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text="Kontoauszug vom 01.01.2024"))
        assert doc.doc_type == DocumentType.BANK_STATEMENT

    def test_tax_filename(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(
            _raw(tmp_path, filename="finanzamt-bescheid.pdf", text="content")
        )
        assert doc.doc_type == DocumentType.TAX
        assert doc.confidence == 0.85

    def test_filename_beats_content(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(
            _raw(tmp_path, filename="rechnung.pdf", text="versicherung policy")
        )
        assert doc.doc_type == DocumentType.INVOICE
        assert doc.confidence == 0.85

    def test_bill_keywords(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text="stromrechnung 2024"))
        assert doc.doc_type == DocumentType.BILL

    def test_insurance_keyword(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text="Versicherung Hausrat 2024"))
        assert doc.doc_type == DocumentType.INSURANCE

    def test_returns_classified_document(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        result = clf.classify(_raw(tmp_path, text="invoice"))
        assert isinstance(result, ClassifiedDocument)


class TestClaudeClassifier:
    def test_classifies_invoice(self, tmp_path: Path) -> None:
        clf = ClaudeClassifier(api_key="sk-test")
        raw = _raw(tmp_path, text="invoice for services")

        data = {
            "doc_type": "invoice",
            "date": "2024-11-01",
            "vendor": "Acme GmbH",
            "amount": 99.0,
            "currency": "EUR",
            "reference": "INV-9912",
            "confidence": 0.95,
        }
        with patch.object(
            clf._client.messages, "create", return_value=_mock_response(data)
        ):
            doc = clf.classify(raw)

        assert doc.doc_type == DocumentType.INVOICE
        assert doc.date == datetime.date(2024, 11, 1)
        assert doc.vendor == "Acme GmbH"
        assert doc.amount == pytest.approx(99.0)
        assert doc.currency == "EUR"
        assert doc.reference == "INV-9912"
        assert doc.confidence == pytest.approx(0.95)

    def test_handles_null_fields(self, tmp_path: Path) -> None:
        clf = ClaudeClassifier(api_key="sk-test")
        data = {
            "doc_type": "other",
            "date": None,
            "vendor": None,
            "amount": None,
            "currency": None,
            "reference": None,
            "confidence": 0.4,
        }
        with patch.object(
            clf._client.messages, "create", return_value=_mock_response(data)
        ):
            doc = clf.classify(_raw(tmp_path, text="document"))

        assert doc.doc_type == DocumentType.OTHER
        assert doc.date is None
        assert doc.vendor is None
        assert doc.confidence == pytest.approx(0.4)

    def test_handles_bad_date_gracefully(self, tmp_path: Path) -> None:
        clf = ClaudeClassifier(api_key="sk-test")
        data = {
            "doc_type": "invoice",
            "date": "not-a-date",
            "vendor": None,
            "amount": None,
            "currency": None,
            "reference": None,
            "confidence": 0.7,
        }
        with patch.object(
            clf._client.messages, "create", return_value=_mock_response(data)
        ):
            doc = clf.classify(_raw(tmp_path, text="invoice"))

        assert doc.date is None

    def test_default_confidence_when_missing(self, tmp_path: Path) -> None:
        clf = ClaudeClassifier(api_key="sk-test")
        data = {"doc_type": "other"}
        with patch.object(
            clf._client.messages, "create", return_value=_mock_response(data)
        ):
            doc = clf.classify(_raw(tmp_path, text="text"))

        assert doc.confidence == pytest.approx(0.5)
