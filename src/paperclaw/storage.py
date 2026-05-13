from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from paperclaw import __version__
from paperclaw._naming import canonical_name, content_hash
from paperclaw.schemas import ClassifiedDocument, LibraryDocument


class FilesystemStorer:
    def __init__(self, library: Path) -> None:
        self._library = library

    def store(
        self, classified: ClassifiedDocument, *, unsorted: bool = False
    ) -> LibraryDocument:
        src = classified.raw.source_path

        if unsorted:
            dest_dir = self._library / "_unsorted"
            hash8 = content_hash(src)
            fname = f"{src.stem}_{hash8}.pdf"
        else:
            fname = canonical_name(classified)
            dest_dir = self._library

        dest_dir.mkdir(parents=True, exist_ok=True)
        target = dest_dir / fname

        if target.exists() and not unsorted:
            hash8 = content_hash(src)
            stem = Path(fname).stem
            target = dest_dir / f"{stem}_{hash8}.pdf"

        shutil.move(str(src), str(target))

        transcript = target.with_suffix(".md")
        _write_sidecar(classified, target, transcript)

        return LibraryDocument(
            classified=classified,
            library_path=target,
            transcript_path=transcript,
            canonical_name=target.name,
        )


def _write_sidecar(
    classified: ClassifiedDocument,
    pdf_path: Path,
    transcript: Path,
) -> None:
    c = classified
    lines: list[str] = [
        f"# {pdf_path.name}",
        "",
        f"**Source**: {c.raw.filename}",
        f"**Extracted**: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}",  # noqa: E501
        f"**PaperClaw**: {__version__}",
        f"**Type**: {c.doc_type}",
        f"**Date**: {c.date or 'unknown'}",
        f"**Vendor**: {c.vendor or 'unknown'}",
    ]
    if c.amount is not None:
        lines.append(f"**Amount**: {c.amount} {c.currency or ''}")
    if c.reference:
        lines.append(f"**Reference**: {c.reference}")
    lines.append(f"**Confidence**: {int(c.confidence * 100)}%")
    lines.extend(["", "## Extracted Text", "", c.raw.text or "*No text extracted.*"])
    transcript.write_text("\n".join(lines), encoding="utf-8")
