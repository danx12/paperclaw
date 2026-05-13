from __future__ import annotations

import datetime
from pathlib import Path

from paperclaw._naming import canonical_name, content_hash, slugify
from paperclaw.schemas import ClassifiedDocument, DocumentType, RawDocument


def _raw(tmp_path: Path, filename: str = "test.pdf") -> RawDocument:
    p = tmp_path / filename
    p.write_bytes(b"data")
    return RawDocument(source_path=p, filename=filename, size_bytes=4, text="")


def _classified(tmp_path: Path, **kwargs: object) -> ClassifiedDocument:
    return ClassifiedDocument(
        raw=_raw(tmp_path), doc_type=DocumentType.INVOICE, confidence=0.9, **kwargs
    )


class TestSlugify:
    def test_lowercases(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_special_chars_become_dash(self) -> None:
        assert slugify("Acme GmbH & Co.") == "acme-gmbh-co"

    def test_consecutive_separators_collapsed(self) -> None:
        assert slugify("foo  --  bar") == "foo-bar"

    def test_empty_returns_fallback(self) -> None:
        assert slugify("") == "unknown"
        assert slugify("---") == "unknown"
        assert slugify("", fallback="noref") == "noref"

    def test_truncates_at_40(self) -> None:
        assert len(slugify("a" * 50)) <= 40

    def test_no_leading_trailing_dash(self) -> None:
        result = slugify("!hello!")
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_numbers_preserved(self) -> None:
        assert slugify("INV-9912") == "inv-9912"


class TestContentHash:
    def test_returns_8_chars(self, tmp_path: Path) -> None:
        p = tmp_path / "f.pdf"
        p.write_bytes(b"test content")
        assert len(content_hash(p)) == 8

    def test_consistent(self, tmp_path: Path) -> None:
        p = tmp_path / "f.pdf"
        p.write_bytes(b"test content")
        assert content_hash(p) == content_hash(p)

    def test_different_content_differs(self, tmp_path: Path) -> None:
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        a.write_bytes(b"aaa")
        b.write_bytes(b"bbb")
        assert content_hash(a) != content_hash(b)

    def test_only_hex_chars(self, tmp_path: Path) -> None:
        p = tmp_path / "f.pdf"
        p.write_bytes(b"data")
        assert all(c in "0123456789abcdef" for c in content_hash(p))


class TestCanonicalName:
    def test_full_metadata(self, tmp_path: Path) -> None:
        doc = _classified(
            tmp_path,
            date=datetime.date(2024, 11, 1),
            vendor="Acme GmbH",
            reference="INV-9912",
        )
        assert canonical_name(doc) == "2024-11-01_invoice_acme-gmbh_inv-9912.pdf"

    def test_no_date_uses_zeros(self, tmp_path: Path) -> None:
        doc = _classified(tmp_path, vendor="Test", reference="REF1")
        assert canonical_name(doc).startswith("0000-00-00_")

    def test_no_reference_uses_noref(self, tmp_path: Path) -> None:
        doc = _classified(
            tmp_path, date=datetime.date(2025, 3, 15), vendor="Vattenfall"
        )
        assert canonical_name(doc).endswith("_noref.pdf")

    def test_no_vendor_uses_unknown(self, tmp_path: Path) -> None:
        doc = _classified(tmp_path, date=datetime.date(2025, 1, 1))
        assert "_unknown_" in canonical_name(doc)

    def test_always_ends_with_pdf(self, tmp_path: Path) -> None:
        doc = _classified(tmp_path)
        assert canonical_name(doc).endswith(".pdf")
