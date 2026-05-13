from __future__ import annotations

from pathlib import Path

import pdfplumber

from paperclaw.schemas import RawDocument


class PdfPlumberExtractor:
    def extract(self, path: Path) -> RawDocument:
        size = path.stat().st_size
        parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
        return RawDocument(
            source_path=path,
            filename=path.name,
            size_bytes=size,
            text="\n".join(parts),
        )
