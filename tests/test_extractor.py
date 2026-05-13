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


def test_png_short_circuits(extractor: PdfPlumberExtractor, tmp_path: Path) -> None:
    png = tmp_path / "scan.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nstub")
    raw = extractor.extract(png)
    assert raw.text == ""
    assert raw.filename == "scan.png"
    assert raw.size_bytes == png.stat().st_size


def test_real_png_returns_empty_text(extractor: PdfPlumberExtractor) -> None:
    """Real PNGs from tests/data produce empty text (no OCR)."""
    pngs = sorted(DATA_DIR.glob("*.png"))
    assert pngs, "No PNG files found in tests/data/ — add at least one"
    for png in pngs:
        raw = extractor.extract(png)
        assert raw.text == "", f"{png.name} should have empty text"
        assert raw.filename == png.name
        assert raw.size_bytes == png.stat().st_size
        assert raw.source_path == png
