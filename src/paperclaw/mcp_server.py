from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from paperclaw._tools import execute_tool
from paperclaw.library_index import LibraryIndex


def create_server(library_root: Path) -> FastMCP:
    """Return a FastMCP server exposing paperclaw's 4 document tools."""
    index = LibraryIndex.load(library_root)
    server = FastMCP("paperclaw")

    @server.tool()
    def list_documents(
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "date_desc",
    ) -> str:
        """List documents in the library with their metadata, paginated.

        Use when the user asks open-ended questions like 'what do I have' or
        to scan through the corpus. Sort by date descending by default.
        sort_by accepts: date_desc, date_asc, name.
        """
        return execute_tool(
            "list_documents",
            {"page": page, "page_size": page_size, "sort_by": sort_by},
            index,
        )

    @server.tool()
    def search_documents(
        doc_type: str | None = None,
        vendor: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        text: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """Filter documents by structured fields (AND-combined), paginated.

        doc_type: invoice, bill, contract, bank_statement, tax, insurance,
        letter, other. vendor: case-insensitive substring match.
        date_from / date_to: inclusive bounds, YYYY-MM-DD.
        text: case-insensitive substring across name, vendor, reference, and
        extracted text.
        """
        args: dict[str, object] = {"page": page, "page_size": page_size}
        if doc_type is not None:
            args["doc_type"] = doc_type
        if vendor is not None:
            args["vendor"] = vendor
        if date_from is not None:
            args["date_from"] = date_from
        if date_to is not None:
            args["date_to"] = date_to
        if text is not None:
            args["text"] = text
        return execute_tool("search_documents", args, index)

    @server.tool()
    def read_document(name: str, max_chars: int = 12000) -> str:
        """Read the full sidecar (metadata + extracted text) for one document.

        Use to answer questions about specific contents once you know the
        canonical name from list_documents or search_documents.
        name: canonical filename, e.g. '2024-11-01_invoice_acme-gmbh_INV-9912.pdf'.
        max_chars: truncate extracted text to this many characters.
        """
        return execute_tool(
            "read_document", {"name": name, "max_chars": max_chars}, index
        )

    @server.tool()
    def grep_documents(
        pattern: str,
        case_sensitive: bool = False,
        max_matches: int = 50,
    ) -> str:
        """Regex search across the extracted text of every document.

        Returns matching lines with their document name and line number. Use to
        find specific identifiers, amounts, or phrases when you don't already
        know which document holds them.
        pattern: Python-flavored regex.
        max_matches: stop after this many matches (max 200).
        """
        return execute_tool(
            "grep_documents",
            {
                "pattern": pattern,
                "case_sensitive": case_sensitive,
                "max_matches": max_matches,
            },
            index,
        )

    return server


def run_stdio(library_root: Path) -> None:
    """Start the MCP server on stdio transport (blocking)."""
    server = create_server(library_root)
    server.run(transport="stdio")
