from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from paperclaw.classifier import LocalRulesClassifier
from paperclaw.extractor import PdfPlumberExtractor
from paperclaw.pipeline import Pipeline
from paperclaw.schemas import (
    ClassifiedDocument,
    DocumentType,
    LibraryDocument,
    RawDocument,
)
from paperclaw.storage import FilesystemStorer

DATA_DIR = Path(__file__).parent / "data"


def _pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.4 stub")
    return path


class _FakeExtractor:
    def __init__(self, text: str = "invoice text") -> None:
        self._text = text

    def extract(self, path: Path) -> RawDocument:
        return RawDocument(
            source_path=path, filename=path.name, size_bytes=4, text=self._text
        )


class _FakeClassifier:
    def __init__(
        self,
        doc_type: DocumentType = DocumentType.INVOICE,
        confidence: float = 0.85,
    ) -> None:
        self._type = doc_type
        self._conf = confidence

    def classify(self, raw: RawDocument) -> ClassifiedDocument:
        return ClassifiedDocument(raw=raw, doc_type=self._type, confidence=self._conf)


class _FakeStorer:
    def __init__(self, library: Path) -> None:
        self.library = library
        self.calls: list[tuple[ClassifiedDocument, bool]] = []

    def store(
        self, classified: ClassifiedDocument, *, unsorted: bool = False
    ) -> LibraryDocument:
        self.calls.append((classified, unsorted))
        name = f"{'_unsorted/' if unsorted else ''}{classified.raw.filename}"
        p = self.library / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"stub")
        md = p.with_suffix(".md")
        md.write_text("sidecar")
        return LibraryDocument(
            classified=classified,
            library_path=p,
            transcript_path=md,
            canonical_name=name,
        )


def _pipeline(
    tmp_path: Path,
    *,
    text: str = "invoice text",
    local_conf: float = 0.85,
    claude_conf: float | None = None,
    threshold: float = 0.75,
    claude_min: float = 0.50,
) -> tuple[Pipeline, _FakeStorer]:
    storer = _FakeStorer(tmp_path / "library")
    claude_clf = (
        _FakeClassifier(confidence=claude_conf) if claude_conf is not None else None
    )
    pipeline = Pipeline(
        extractor=_FakeExtractor(text=text),
        local_classifier=_FakeClassifier(confidence=local_conf),
        storer=storer,
        claude_classifier=claude_clf,
        threshold=threshold,
        claude_min=claude_min,
    )
    return pipeline, storer


def test_high_confidence_stores_directly(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _pdf(inbox / "test.pdf")

    pipeline, storer = _pipeline(tmp_path, local_conf=0.85)
    results = pipeline.run(inbox)

    assert len(results) == 1
    assert storer.calls[0][1] is False


def test_low_confidence_no_claude_routes_unsorted(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _pdf(inbox / "test.pdf")

    pipeline, storer = _pipeline(tmp_path, local_conf=0.30)
    pipeline.run(inbox)

    assert storer.calls[0][1] is True


def test_empty_text_routes_unsorted(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _pdf(inbox / "test.pdf")

    pipeline, storer = _pipeline(tmp_path, text="")
    pipeline.run(inbox)

    assert storer.calls[0][1] is True


def test_png_discovered(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "scan.png").write_bytes(b"\x89PNG\r\n\x1a\nstub")

    pipeline, storer = _pipeline(tmp_path, text="", local_conf=0.0)
    pipeline.run(inbox)

    assert len(storer.calls) == 1
    assert storer.calls[0][0].raw.filename == "scan.png"
    assert storer.calls[0][1] is True


def test_empty_text_with_claude_routes_via_claude(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _pdf(inbox / "scan.pdf")

    pipeline, storer = _pipeline(tmp_path, text="", local_conf=0.0, claude_conf=0.85)
    pipeline.run(inbox)

    assert storer.calls[0][1] is False


def test_claude_high_confidence_stores_directly(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _pdf(inbox / "test.pdf")

    pipeline, storer = _pipeline(tmp_path, local_conf=0.30, claude_conf=0.80)
    pipeline.run(inbox)

    assert storer.calls[0][1] is False


def test_claude_low_confidence_routes_unsorted(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _pdf(inbox / "test.pdf")

    pipeline, storer = _pipeline(tmp_path, local_conf=0.30, claude_conf=0.30)
    pipeline.run(inbox)

    assert storer.calls[0][1] is True


def test_extraction_failure_routes_unsorted(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _pdf(inbox / "bad.pdf")

    class _ErrorExtractor:
        def extract(self, path: Path) -> RawDocument:
            raise ValueError("corrupt")

    storer = _FakeStorer(tmp_path / "library")
    pipeline = Pipeline(
        extractor=_ErrorExtractor(),
        local_classifier=_FakeClassifier(),
        storer=storer,
        threshold=0.75,
    )
    results = pipeline.run(inbox)

    assert len(results) == 1
    assert storer.calls[0][1] is True


def test_one_bad_file_does_not_abort_batch(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _pdf(inbox / "a.pdf")
    _pdf(inbox / "b.pdf")

    call_count = 0

    class _SometimesError:
        def extract(self, path: Path) -> RawDocument:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("first fails")
            return RawDocument(
                source_path=path, filename=path.name, size_bytes=4, text="invoice"
            )

    storer = _FakeStorer(tmp_path / "library")
    pipeline = Pipeline(
        extractor=_SometimesError(),
        local_classifier=_FakeClassifier(confidence=0.85),
        storer=storer,
        threshold=0.75,
    )
    results = pipeline.run(inbox)

    assert len(results) == 2


def test_empty_inbox_returns_empty_list(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    pipeline, storer = _pipeline(tmp_path)
    results = pipeline.run(inbox)

    assert results == []


def test_claude_failure_falls_back_to_unsorted(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    _pdf(inbox / "test.pdf")

    class _ErrorClaude:
        def classify(self, raw: RawDocument) -> ClassifiedDocument:
            raise RuntimeError("API down")

    storer = _FakeStorer(tmp_path / "library")
    pipeline = Pipeline(
        extractor=_FakeExtractor(text="some text"),
        local_classifier=_FakeClassifier(confidence=0.30),
        storer=storer,
        claude_classifier=_ErrorClaude(),
        threshold=0.75,
    )
    results = pipeline.run(inbox)

    assert len(results) == 1
    assert storer.calls[0][1] is True


@pytest.mark.integration
def test_integration_stromrechnung(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    shutil.copy(
        DATA_DIR / "stadtwerke-stromrechnung.pdf",
        inbox / "stadtwerke-stromrechnung.pdf",
    )

    pipeline = Pipeline(
        extractor=PdfPlumberExtractor(),
        local_classifier=LocalRulesClassifier(),
        storer=FilesystemStorer(tmp_path / "library"),
        threshold=0.75,
    )
    results = pipeline.run(inbox)

    assert len(results) == 1
    assert results[0].library_path.exists()
    assert results[0].transcript_path.exists()


@pytest.mark.integration
def test_integration_finanzamt(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    shutil.copy(DATA_DIR / "finanzamt-bescheid.pdf", inbox / "finanzamt-bescheid.pdf")

    pipeline = Pipeline(
        extractor=PdfPlumberExtractor(),
        local_classifier=LocalRulesClassifier(),
        storer=FilesystemStorer(tmp_path / "library"),
        threshold=0.75,
    )
    results = pipeline.run(inbox)

    assert len(results) == 1
    assert results[0].library_path.exists()
