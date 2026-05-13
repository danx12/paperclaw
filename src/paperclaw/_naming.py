from __future__ import annotations

import hashlib
import re
from pathlib import Path

from paperclaw.schemas import ClassifiedDocument


def slugify(text: str, fallback: str = "unknown") -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")[:40].strip("-")
    return text or fallback


def content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def canonical_name(doc: ClassifiedDocument) -> str:
    date_str = doc.date.strftime("%Y-%m-%d") if doc.date else "0000-00-00"
    type_str = str(doc.doc_type)
    vendor_str = slugify(doc.vendor or "", fallback="unknown")
    ref_str = slugify(doc.reference or "", fallback="noref")
    return f"{date_str}_{type_str}_{vendor_str}_{ref_str}.pdf"
