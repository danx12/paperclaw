from __future__ import annotations

import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class DocumentType(StrEnum):
    INVOICE = "invoice"
    BILL = "bill"
    CONTRACT = "contract"
    BANK_STATEMENT = "bank_statement"
    TAX = "tax"
    INSURANCE = "insurance"
    LETTER = "letter"
    OTHER = "other"


class RawDocument(BaseModel):
    source_path: Path
    filename: str
    size_bytes: int
    text: str

    model_config = {"frozen": True}


class ClassifiedDocument(BaseModel):
    raw: RawDocument
    doc_type: DocumentType
    date: datetime.date | None = None
    vendor: str | None = None
    amount: float | None = None
    currency: str | None = Field(default=None, max_length=3)
    reference: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = {"frozen": True}


class LibraryDocument(BaseModel):
    classified: ClassifiedDocument
    library_path: Path
    transcript_path: Path
    canonical_name: str

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _sidecar_must_be_markdown(self) -> LibraryDocument:
        if self.transcript_path.suffix != ".md":
            raise ValueError("transcript_path must have a .md suffix")
        return self
