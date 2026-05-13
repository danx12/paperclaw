from __future__ import annotations

from pathlib import Path
from typing import Protocol

from paperclaw.schemas import ClassifiedDocument, LibraryDocument, RawDocument


class Extractor(Protocol):
    def extract(self, path: Path) -> RawDocument: ...


class Classifier(Protocol):
    def classify(self, raw: RawDocument) -> ClassifiedDocument: ...


class Storer(Protocol):
    def store(
        self, classified: ClassifiedDocument, *, unsorted: bool = False
    ) -> LibraryDocument: ...
