from __future__ import annotations

import datetime
from pathlib import Path

from paperclaw.schemas import ClassifiedDocument, DocumentType, RawDocument
from paperclaw.storage import FilesystemStorer


def _pdf(tmp_path: Path, name: str = "test.pdf", content: bytes = b"%PDF stub") -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def _classified(
    tmp_path: Path,
    filename: str = "test.pdf",
    content: bytes = b"%PDF stub",
    doc_type: DocumentType = DocumentType.INVOICE,
    confidence: float = 0.85,
    **kwargs: object,
) -> ClassifiedDocument:
    pdf = _pdf(tmp_path, filename, content)
    raw = RawDocument(
        source_path=pdf,
        filename=filename,
        size_bytes=pdf.stat().st_size,
        text="invoice",
    )
    return ClassifiedDocument(
        raw=raw, doc_type=doc_type, confidence=confidence, **kwargs
    )


def test_stores_sorted_pdf(tmp_path: Path) -> None:
    library = tmp_path / "library"
    storer = FilesystemStorer(library)
    classified = _classified(
        tmp_path,
        doc_type=DocumentType.INVOICE,
        date=datetime.date(2024, 11, 1),
        vendor="Acme GmbH",
        reference="INV-9912",
    )
    lib_doc = storer.store(classified)

    assert lib_doc.library_path.exists()
    assert lib_doc.transcript_path.exists()
    assert lib_doc.library_path.suffix == ".pdf"
    assert "2024-11-01" in lib_doc.canonical_name
    assert "invoice" in lib_doc.canonical_name


def test_stores_unsorted_pdf(tmp_path: Path) -> None:
    library = tmp_path / "library"
    storer = FilesystemStorer(library)
    classified = _classified(tmp_path)
    lib_doc = storer.store(classified, unsorted=True)

    assert "_unsorted" in str(lib_doc.library_path)
    assert lib_doc.library_path.exists()
    assert lib_doc.transcript_path.exists()


def test_sidecar_contains_metadata(tmp_path: Path) -> None:
    library = tmp_path / "library"
    storer = FilesystemStorer(library)
    classified = _classified(
        tmp_path,
        doc_type=DocumentType.INVOICE,
        date=datetime.date(2024, 11, 1),
        vendor="Acme GmbH",
        amount=99.0,
        currency="EUR",
        reference="INV-9912",
        confidence=0.9,
    )
    lib_doc = storer.store(classified)
    content = lib_doc.transcript_path.read_text()

    assert "invoice" in content
    assert "Acme GmbH" in content
    assert "2024-11-01" in content
    assert "INV-9912" in content
    assert "90%" in content
    assert "## Extracted Text" in content


def test_sidecar_stem_matches_pdf(tmp_path: Path) -> None:
    library = tmp_path / "library"
    storer = FilesystemStorer(library)
    lib_doc = storer.store(_classified(tmp_path))

    assert lib_doc.transcript_path.stem == lib_doc.library_path.stem


def test_source_file_moved(tmp_path: Path) -> None:
    library = tmp_path / "library"
    storer = FilesystemStorer(library)
    classified = _classified(tmp_path)
    src = classified.raw.source_path

    storer.store(classified)

    assert not src.exists()


def test_collision_appends_hash(tmp_path: Path) -> None:
    library = tmp_path / "library"
    storer = FilesystemStorer(library)

    kwargs = dict(
        doc_type=DocumentType.INVOICE,
        date=datetime.date(2024, 11, 1),
        vendor="Acme",
        reference="INV-1",
    )
    classified1 = _classified(
        tmp_path, filename="a.pdf", content=b"content-a", **kwargs
    )
    lib_doc1 = storer.store(classified1)

    classified2 = _classified(
        tmp_path, filename="b.pdf", content=b"content-b", **kwargs
    )
    lib_doc2 = storer.store(classified2)

    assert lib_doc1.library_path != lib_doc2.library_path
    assert lib_doc1.library_path.exists()
    assert lib_doc2.library_path.exists()


def test_library_directories_created(tmp_path: Path) -> None:
    library = tmp_path / "deep" / "library"
    storer = FilesystemStorer(library)
    classified = _classified(tmp_path)
    lib_doc = storer.store(classified, unsorted=True)

    assert lib_doc.library_path.parent.exists()


def test_unsorted_name_includes_hash(tmp_path: Path) -> None:
    library = tmp_path / "library"
    storer = FilesystemStorer(library)
    classified = _classified(tmp_path, filename="my-doc.pdf")
    lib_doc = storer.store(classified, unsorted=True)

    assert lib_doc.canonical_name.startswith("my-doc_")
    assert lib_doc.canonical_name.endswith(".pdf")
    assert len(lib_doc.canonical_name) == len("my-doc_") + 8 + len(".pdf")
