from __future__ import annotations

from pathlib import Path

import pytest

from paperclaw.extractor import PdfPlumberExtractor

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def extractor() -> PdfPlumberExtractor:
    return PdfPlumberExtractor()


def test_extracts_stromrechnung(extractor: PdfPlumberExtractor) -> None:
    pdf = DATA_DIR / "stadtwerke-stromrechnung.pdf"
    raw = extractor.extract(pdf)
    assert raw.filename == "stadtwerke-stromrechnung.pdf"
    assert raw.source_path == pdf
    assert raw.size_bytes > 0
    assert raw.size_bytes == pdf.stat().st_size


def test_extracts_finanzamt(extractor: PdfPlumberExtractor) -> None:
    pdf = DATA_DIR / "finanzamt-bescheid.pdf"
    raw = extractor.extract(pdf)
    assert raw.size_bytes > 0


def test_text_is_string(extractor: PdfPlumberExtractor) -> None:
    pdf = DATA_DIR / "stadtwerke-stromrechnung.pdf"
    raw = extractor.extract(pdf)
    assert isinstance(raw.text, str)


def test_missing_file_raises(extractor: PdfPlumberExtractor, tmp_path: Path) -> None:
    with pytest.raises(Exception):
        extractor.extract(tmp_path / "nonexistent.pdf")
