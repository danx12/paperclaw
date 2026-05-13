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

    # --- new types ---

    def test_receipt_filename(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(
            _raw(tmp_path, filename="kassenbon-rewe.pdf", text="content")
        )
        assert doc.doc_type == DocumentType.RECEIPT
        assert doc.confidence == 0.85

    def test_receipt_content(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text="Quittung Nr. 42\nSumme 9.99 EUR"))
        assert doc.doc_type == DocumentType.RECEIPT

    def test_receipt_english_keyword(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text="Thank you for your purchase\nreceipt"))
        assert doc.doc_type == DocumentType.RECEIPT

    def test_payslip_filename(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(
            _raw(tmp_path, filename="gehaltsabrechnung-2024-01.pdf", text="x")
        )
        assert doc.doc_type == DocumentType.PAYSLIP
        assert doc.confidence == 0.85

    def test_payslip_content(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text="Lohnabrechnung Monat Januar 2024"))
        assert doc.doc_type == DocumentType.PAYSLIP

    def test_medical_filename(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, filename="arztrechnung-2024.pdf", text="x"))
        assert doc.doc_type == DocumentType.MEDICAL
        assert doc.confidence == 0.85

    def test_medical_content_german(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(
            _raw(tmp_path, text="Krankenhaus Berlin\nRechnung Behandlung")
        )
        assert doc.doc_type == DocumentType.MEDICAL

    def test_medical_content_english(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text="Lab result: blood panel negative"))
        assert doc.doc_type == DocumentType.MEDICAL

    def test_warranty_filename(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, filename="garantieschein-tv.pdf", text="x"))
        assert doc.doc_type == DocumentType.WARRANTY
        assert doc.confidence == 0.85

    def test_warranty_content(self, tmp_path: Path) -> None:
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, text="Garantie 2 Jahre ab Kaufdatum"))
        assert doc.doc_type == DocumentType.WARRANTY

    def test_receipt_beats_invoice_on_filename(self, tmp_path: Path) -> None:
        # "kassenbon" should win over generic "rechnung" body text
        clf = LocalRulesClassifier()
        doc = clf.classify(_raw(tmp_path, filename="kassenbon.pdf", text="rechnung"))
        assert doc.doc_type == DocumentType.RECEIPT

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

    def test_vision_path_for_image_only_pdf(self, tmp_path: Path) -> None:
        clf = ClaudeClassifier(api_key="sk-test")
        raw = _raw(tmp_path, filename="scan.pdf", text="")
        data = {
            "extracted_text": "INVOICE\nAcme GmbH\nTotal 99 EUR",
            "doc_type": "invoice",
            "date": "2024-11-01",
            "vendor": "Acme GmbH",
            "amount": 99.0,
            "currency": "EUR",
            "reference": "INV-9912",
            "confidence": 0.9,
        }
        with patch.object(
            clf._client.messages, "create", return_value=_mock_response(data)
        ) as mock:
            doc = clf.classify(raw)

        kwargs = mock.call_args.kwargs
        content = kwargs["messages"][0]["content"]
        assert content[0]["type"] == "document"
        assert content[0]["source"]["media_type"] == "application/pdf"
        assert content[0]["source"]["type"] == "base64"
        assert doc.doc_type == DocumentType.INVOICE
        assert doc.vendor == "Acme GmbH"
        assert "INVOICE" in doc.raw.text

    def test_vision_path_for_png(self, tmp_path: Path) -> None:
        clf = ClaudeClassifier(api_key="sk-test")
        png = tmp_path / "receipt.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\nstub")
        raw = RawDocument(
            source_path=png, filename="receipt.png", size_bytes=4, text=""
        )
        data = {
            "extracted_text": "Receipt body",
            "doc_type": "bill",
            "date": None,
            "vendor": "Stadtwerke",
            "amount": None,
            "currency": None,
            "reference": None,
            "confidence": 0.8,
        }
        with patch.object(
            clf._client.messages, "create", return_value=_mock_response(data)
        ) as mock:
            doc = clf.classify(raw)

        content = mock.call_args.kwargs["messages"][0]["content"]
        assert content[0]["type"] == "image"
        assert content[0]["source"]["media_type"] == "image/png"
        assert doc.doc_type == DocumentType.BILL
        assert doc.raw.text == "Receipt body"
