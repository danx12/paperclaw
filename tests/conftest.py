from __future__ import annotations

from pathlib import Path

import pytest

from paperclaw.schemas import (
    ClassifiedDocument,
    DocumentType,
    RawDocument,
)

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block load_dotenv so .env never leaks into the test process."""
    monkeypatch.setattr("paperclaw.cli.load_dotenv", lambda **_kw: None)


@pytest.fixture
def invoice_pdf() -> Path:
    return DATA_DIR / "stadtwerke-stromrechnung.pdf"


@pytest.fixture
def tax_pdf() -> Path:
    return DATA_DIR / "finanzamt-bescheid.pdf"


@pytest.fixture
def inbox(tmp_path: Path) -> Path:
    d = tmp_path / "inbox"
    d.mkdir()
    return d


@pytest.fixture
def library(tmp_path: Path) -> Path:
    d = tmp_path / "library"
    d.mkdir()
    return d


def make_raw(
    tmp_path: Path,
    filename: str = "test.pdf",
    text: str = "invoice text",
    content: bytes = b"%PDF-1.4 stub",
) -> RawDocument:
    pdf = tmp_path / filename
    pdf.write_bytes(content)
    return RawDocument(
        source_path=pdf,
        filename=filename,
        size_bytes=pdf.stat().st_size,
        text=text,
    )


def make_classified(
    tmp_path: Path,
    doc_type: DocumentType = DocumentType.INVOICE,
    confidence: float = 0.85,
    filename: str = "test.pdf",
    text: str = "invoice text",
    content: bytes = b"%PDF-1.4 stub",
    **kwargs: object,
) -> ClassifiedDocument:
    raw = make_raw(tmp_path, filename=filename, text=text, content=content)
    return ClassifiedDocument(
        raw=raw, doc_type=doc_type, confidence=confidence, **kwargs
    )
