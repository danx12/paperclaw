from __future__ import annotations

import datetime
import json
from typing import Any

from paperclaw.library_index import LibraryEntry, LibraryIndex

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
SIDECAR_BODY_PREVIEW_CHARS = 12000
SNIPPET_CONTEXT_CHARS = 80

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_documents",
        "description": (
            "List documents in the library with their metadata, paginated. "
            "Use this when the user asks open-ended questions like 'what do I have' "
            "or to scan through the corpus. Sort by date descending by default."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "1-indexed page number. Defaults to 1.",
                },
                "page_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_PAGE_SIZE,
                    "description": f"Items per page (max {MAX_PAGE_SIZE}). "
                    f"Defaults to {DEFAULT_PAGE_SIZE}.",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["date_desc", "date_asc", "name"],
                    "description": "Ordering. Defaults to date_desc.",
                },
            },
        },
    },
    {
        "name": "search_documents",
        "description": (
            "Filter documents by structured fields. All filters are AND-combined. "
            "Returns paginated metadata. Use this when the user asks for documents "
            "of a specific type, vendor, date range, or containing a keyword."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_type": {
                    "type": "string",
                    "enum": [
                        "invoice",
                        "bill",
                        "receipt",
                        "contract",
                        "bank_statement",
                        "tax",
                        "insurance",
                        "payslip",
                        "medical",
                        "warranty",
                        "letter",
                        "other",
                    ],
                },
                "vendor": {
                    "type": "string",
                    "description": "Case-insensitive substring match against vendor.",
                },
                "date_from": {
                    "type": "string",
                    "description": "Inclusive lower bound, YYYY-MM-DD.",
                },
                "date_to": {
                    "type": "string",
                    "description": "Inclusive upper bound, YYYY-MM-DD.",
                },
                "text": {
                    "type": "string",
                    "description": "Case-insensitive substring search across name, "
                    "vendor, reference, and extracted text.",
                },
                "page": {"type": "integer", "minimum": 1},
                "page_size": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_PAGE_SIZE,
                },
            },
        },
    },
    {
        "name": "read_document",
        "description": (
            "Read the full sidecar (metadata + extracted text) for one document. "
            "Use this to answer questions about specific contents once you know the "
            "canonical name from list_documents or search_documents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Canonical filename, e.g. "
                    "'2024-11-01_invoice_acme-gmbh_INV-9912.pdf'.",
                },
                "max_chars": {
                    "type": "integer",
                    "minimum": 500,
                    "description": "Truncate the extracted text to this many chars. "
                    f"Defaults to {SIDECAR_BODY_PREVIEW_CHARS}. "
                    "Use a larger value if the doc was truncated and you need more.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "grep_documents",
        "description": (
            "Regex search across the extracted text of every document. Returns "
            "matching lines with their document name and line number. Use this to "
            "find specific identifiers, amounts, or phrases when you don't already "
            "know which document holds them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Python-flavored regex.",
                },
                "case_sensitive": {"type": "boolean"},
                "max_matches": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Stop after this many matches. Defaults to 50.",
                },
            },
            "required": ["pattern"],
        },
    },
]


def execute_tool(name: str, tool_input: dict[str, Any], index: LibraryIndex) -> str:
    if name == "list_documents":
        return _list(index, tool_input)
    if name == "search_documents":
        return _search(index, tool_input)
    if name == "read_document":
        return _read(index, tool_input)
    if name == "grep_documents":
        return _grep(index, tool_input)
    return json.dumps({"error": f"unknown tool: {name}"})


def _list(index: LibraryIndex, args: dict[str, Any]) -> str:
    page = max(1, int(args.get("page", 1)))
    page_size = min(
        MAX_PAGE_SIZE, max(1, int(args.get("page_size", DEFAULT_PAGE_SIZE)))
    )
    sort_by = args.get("sort_by", "date_desc")

    entries = list(index)
    if sort_by == "date_desc":
        entries.sort(key=_date_key, reverse=True)
    elif sort_by == "date_asc":
        entries.sort(key=_date_key)
    elif sort_by == "name":
        entries.sort(key=lambda e: e.canonical_name)

    return _paginate(entries, page, page_size)


def _search(index: LibraryIndex, args: dict[str, Any]) -> str:
    page = max(1, int(args.get("page", 1)))
    page_size = min(
        MAX_PAGE_SIZE, max(1, int(args.get("page_size", DEFAULT_PAGE_SIZE)))
    )
    date_from = _parse_date(args.get("date_from"))
    date_to = _parse_date(args.get("date_to"))
    entries = index.filter(
        doc_type=args.get("doc_type"),
        vendor=args.get("vendor"),
        date_from=date_from,
        date_to=date_to,
        text=args.get("text"),
    )
    return _paginate(entries, page, page_size)


def _read(index: LibraryIndex, args: dict[str, Any]) -> str:
    name = args["name"]
    entry = index.get(name)
    if entry is None:
        return json.dumps(
            {
                "error": f"no document named {name!r}",
                "hint": (
                    "Use list_documents or search_documents to find the exact name."
                ),
            }
        )
    max_chars = int(args.get("max_chars", SIDECAR_BODY_PREVIEW_CHARS))
    body = entry.text
    truncated = False
    if len(body) > max_chars:
        body = body[:max_chars]
        truncated = True

    payload = {
        "canonical_name": entry.canonical_name,
        "doc_type": entry.doc_type,
        "date": entry.date.isoformat() if entry.date else None,
        "vendor": entry.vendor,
        "amount": entry.amount,
        "reference": entry.reference,
        "confidence": entry.confidence,
        "unsorted": entry.unsorted,
        "source": entry.source,
        "extracted_text": body,
        "text_truncated": truncated,
        "full_text_chars": len(entry.text),
    }
    return json.dumps(payload, ensure_ascii=False)


def _grep(index: LibraryIndex, args: dict[str, Any]) -> str:
    pattern = args["pattern"]
    case_sensitive = bool(args.get("case_sensitive", False))
    max_matches = min(200, max(1, int(args.get("max_matches", 50))))
    try:
        hits = index.grep(
            pattern, case_sensitive=case_sensitive, max_matches=max_matches
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    snippets = []
    for entry, lineno, line in hits:
        snippets.append(
            {
                "document": entry.canonical_name,
                "line": lineno,
                "snippet": line[:SNIPPET_CONTEXT_CHARS],
            }
        )
    return json.dumps(
        {
            "pattern": pattern,
            "case_sensitive": case_sensitive,
            "match_count": len(snippets),
            "truncated": len(snippets) >= max_matches,
            "matches": snippets,
        },
        ensure_ascii=False,
    )


def _paginate(entries: list[LibraryEntry], page: int, page_size: int) -> str:
    total = len(entries)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    slice_ = entries[start : start + page_size]

    rows = [
        e.model_dump(
            mode="json",
            include={
                "canonical_name",
                "doc_type",
                "date",
                "vendor",
                "reference",
                "amount",
                "confidence",
                "unsorted",
            },
        )
        for e in slice_
    ]

    return json.dumps(
        {
            "page": page,
            "page_size": page_size,
            "total_results": total,
            "total_pages": total_pages,
            "has_more": page < total_pages,
            "results": rows,
        },
        ensure_ascii=False,
        default=str,
    )


def _date_key(entry: LibraryEntry) -> datetime.date:
    return entry.date or datetime.date.min


def _parse_date(value: Any) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        return None
