from __future__ import annotations

import datetime
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel

_FIELD_RE = re.compile(r"^\*\*([A-Za-z]+)\*\*:\s*(.*)$")
_H1_RE = re.compile(r"^#\s+(.+?)\s*$")
_BODY_MARKER = "## Extracted Text"


class LibraryEntry(BaseModel):
    """A single sidecar parsed from the library."""

    canonical_name: str
    pdf_path: Path  # actual asset path (PDF or PNG); name kept for compatibility
    sidecar_path: Path
    source: str | None = None
    doc_type: str | None = None
    date: datetime.date | None = None
    vendor: str | None = None
    amount: str | None = None
    reference: str | None = None
    confidence: int | None = None
    unsorted: bool = False
    text: str = ""

    model_config = {"frozen": True}

    def as_metadata_row(self) -> str:
        date = self.date.isoformat() if self.date else "0000-00-00"
        vendor = self.vendor or "-"
        ref = self.reference or "-"
        amount = self.amount or "-"
        flag = " [unsorted]" if self.unsorted else ""
        return (
            f"{self.canonical_name} | {date} | {self.doc_type or '-'} | "
            f"{vendor} | {ref} | {amount}{flag}"
        )


class LibraryIndex:
    """In-memory index of sidecar metadata + full text bodies."""

    def __init__(self, entries: list[LibraryEntry], root: Path) -> None:
        self._entries = entries
        self._by_name = {e.canonical_name: e for e in entries}
        self._root = root

    @classmethod
    def load(cls, library_root: Path) -> LibraryIndex:
        entries: list[LibraryEntry] = []
        for md in sorted(library_root.rglob("*.md")):
            entry = _parse_sidecar(md, library_root)
            if entry is not None:
                entries.append(entry)
        return cls(entries, library_root)

    @property
    def root(self) -> Path:
        return self._root

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[LibraryEntry]:
        return iter(self._entries)

    def get(self, canonical_name: str) -> LibraryEntry | None:
        return self._by_name.get(canonical_name)

    def filter(
        self,
        doc_type: str | None = None,
        vendor: str | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        text: str | None = None,
    ) -> list[LibraryEntry]:
        out: list[LibraryEntry] = []
        text_lc = text.lower() if text else None
        vendor_lc = vendor.lower() if vendor else None
        for e in self._entries:
            if doc_type and (e.doc_type or "") != doc_type:
                continue
            if vendor_lc and vendor_lc not in (e.vendor or "").lower():
                continue
            if date_from and (e.date is None or e.date < date_from):
                continue
            if date_to and (e.date is None or e.date > date_to):
                continue
            if text_lc:
                haystack = " ".join(
                    [e.canonical_name, e.vendor or "", e.reference or "", e.text]
                ).lower()
                if text_lc not in haystack:
                    continue
            out.append(e)
        return out

    def grep(
        self,
        pattern: str,
        *,
        case_sensitive: bool = False,
        max_matches: int = 50,
    ) -> list[tuple[LibraryEntry, int, str]]:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc
        hits: list[tuple[LibraryEntry, int, str]] = []
        for e in self._entries:
            for lineno, line in enumerate(e.text.splitlines(), start=1):
                if regex.search(line):
                    hits.append((e, lineno, line.strip()))
                    if len(hits) >= max_matches:
                        return hits
        return hits


def render_metadata_table(entries: Iterable[LibraryEntry]) -> str:
    rows = ["name | date | type | vendor | reference | amount"]
    for e in entries:
        rows.append(e.as_metadata_row())
    return "\n".join(rows)


def _parse_sidecar(path: Path, library_root: Path) -> LibraryEntry | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    fields: dict[str, str] = {}
    body_lines: list[str] = []
    in_body = False
    h1: str | None = None
    for line in raw.splitlines():
        if not in_body:
            if line.strip() == _BODY_MARKER:
                in_body = True
                continue
            if h1 is None:
                m1 = _H1_RE.match(line)
                if m1:
                    h1 = m1.group(1)
                    continue
            match = _FIELD_RE.match(line)
            if match:
                fields[match.group(1).lower()] = match.group(2).strip()
        else:
            body_lines.append(line)

    text = "\n".join(body_lines).strip("\n")

    # Prefer the H1 (carries the correct suffix for PDF/PNG/etc.); fall back to
    # the sidecar stem with a .pdf suffix for older sidecars.
    canonical_name = h1 or path.with_suffix(".pdf").name
    asset_path = path.with_name(canonical_name)
    unsorted = path.parent.name == "_unsorted"

    date: datetime.date | None = None
    raw_date = fields.get("date")
    if raw_date and raw_date != "unknown" and raw_date != "0000-00-00":
        try:
            date = datetime.date.fromisoformat(raw_date)
        except ValueError:
            date = None

    confidence: int | None = None
    raw_conf = fields.get("confidence")
    if raw_conf:
        digits = re.match(r"(\d+)", raw_conf)
        if digits:
            confidence = int(digits.group(1))

    vendor = fields.get("vendor")
    if vendor in ("unknown", ""):
        vendor = None
    reference = fields.get("reference")
    if reference in ("noref", ""):
        reference = None

    return LibraryEntry(
        canonical_name=canonical_name,
        pdf_path=asset_path,
        sidecar_path=path,
        source=fields.get("source"),
        doc_type=fields.get("type"),
        date=date,
        vendor=vendor,
        amount=fields.get("amount"),
        reference=reference,
        confidence=confidence,
        unsorted=unsorted,
        text=text,
    )
