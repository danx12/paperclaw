from __future__ import annotations

import logging
from itertools import chain
from pathlib import Path

from paperclaw.protocols import Classifier, Extractor, Storer
from paperclaw.schemas import (
    ClassifiedDocument,
    DocumentType,
    LibraryDocument,
    RawDocument,
)

logger = logging.getLogger(__name__)

SUPPORTED_GLOBS = ("*.pdf", "*.png")


def iter_inputs(inbox: Path) -> list[Path]:
    return sorted(chain.from_iterable(inbox.glob(p) for p in SUPPORTED_GLOBS))


class Pipeline:
    def __init__(
        self,
        extractor: Extractor,
        local_classifier: Classifier,
        storer: Storer,
        claude_classifier: Classifier | None = None,
        threshold: float = 0.75,
        claude_min: float = 0.50,
    ) -> None:
        self._extractor = extractor
        self._local = local_classifier
        self._storer = storer
        self._claude = claude_classifier
        self._threshold = threshold
        self._claude_min = claude_min

    def run(self, inbox: Path) -> list[LibraryDocument]:
        results: list[LibraryDocument] = []
        for path in iter_inputs(inbox):
            try:
                results.append(self.process_file(path))
            except Exception as exc:
                logger.error("Unhandled error processing %s: %s", path.name, exc)
        return results

    def process_file(self, path: Path) -> LibraryDocument:
        try:
            raw = self._extractor.extract(path)
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", path.name, exc)
            raw = RawDocument(
                source_path=path,
                filename=path.name,
                size_bytes=path.stat().st_size,
                text="",
            )
            fallback = ClassifiedDocument(
                raw=raw, doc_type=DocumentType.OTHER, confidence=0.0
            )
            return self._storer.store(fallback, unsorted=True)

        if self._claude is not None:
            try:
                result = self._claude.classify(raw)
            except Exception as exc:
                logger.warning(
                    "Claude classification failed for %s: %s", path.name, exc
                )
                result = self._local.classify(raw)
                return self._storer.store(result, unsorted=True)

            if result.confidence >= self._claude_min:
                return self._storer.store(result)
            return self._storer.store(result, unsorted=True)

        if not raw.text.strip():
            return self._storer.store(self._local.classify(raw), unsorted=True)

        classified = self._local.classify(raw)
        if classified.confidence >= self._threshold:
            return self._storer.store(classified)
        return self._storer.store(classified, unsorted=True)
