from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from paperclaw.mcp_server import create_server

# Suppress MCP's INFO-level request logs during testing.
logging.getLogger("mcp").setLevel(logging.WARNING)

SIDECAR_A = """\
# 2024-01-15_invoice_acme_INV-1.pdf

**Type**: invoice
**Date**: 2024-01-15
**Vendor**: Acme Corp
**Amount**: 100.0 EUR
**Reference**: INV-1
**Confidence**: 90%

## Extracted Text

Acme invoice for consulting services.
Total: 100.00 EUR
"""

SIDECAR_B = """\
# 2024-06-10_bill_stadtwerke_R-22.pdf

**Type**: bill
**Date**: 2024-06-10
**Vendor**: Stadtwerke München
**Reference**: R-22
**Confidence**: 88%

## Extracted Text

Stromrechnung Juni 2024
Kundennummer 99999
"""


@pytest.fixture
def library_root(tmp_path: Path) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "2024-01-15_invoice_acme_INV-1.md").write_text(SIDECAR_A, encoding="utf-8")
    (lib / "2024-06-10_bill_stadtwerke_R-22.md").write_text(SIDECAR_B, encoding="utf-8")
    return lib


@pytest.fixture
def server(library_root: Path) -> FastMCP:
    return create_server(library_root)


# ---------------------------------------------------------------------------
# Structural tests (synchronous)
# ---------------------------------------------------------------------------


def test_create_server_returns_fastmcp(server: FastMCP) -> None:
    assert isinstance(server, FastMCP)
    assert server.name == "paperclaw"


def test_server_exposes_four_tools(server: FastMCP) -> None:
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "list_documents",
        "search_documents",
        "read_document",
        "grep_documents",
    }


def test_tools_have_descriptions(server: FastMCP) -> None:
    tools = asyncio.run(server.list_tools())
    for tool in tools:
        assert tool.description, f"tool '{tool.name}' has no description"


# ---------------------------------------------------------------------------
# Protocol-level tests via in-process MCP client
# ---------------------------------------------------------------------------


def _run(coro):  # type: ignore[no-untyped-def]
    """Convenience wrapper so test functions stay synchronous."""
    return asyncio.run(coro)


def test_protocol_list_tools(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.list_tools()
            names = {t.name for t in result.tools}
            assert names == {
                "list_documents",
                "search_documents",
                "read_document",
                "grep_documents",
            }

    _run(_test())


def test_list_documents_returns_both_entries(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "list_documents", {"page": 1, "page_size": 10}
            )
            text = result.content[0].text
            payload = json.loads(text)
            assert payload["total_results"] == 2
            assert payload["has_more"] is False

    _run(_test())


def test_list_documents_paginates(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "list_documents", {"page": 1, "page_size": 1}
            )
            payload = json.loads(result.content[0].text)
            assert payload["total_results"] == 2
            assert payload["total_pages"] == 2
            assert len(payload["results"]) == 1

    _run(_test())


def test_list_documents_sort_by_date_desc(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool("list_documents", {"sort_by": "date_desc"})
            payload = json.loads(result.content[0].text)
            dates = [r["date"] for r in payload["results"]]
            assert dates == sorted(dates, reverse=True)

    _run(_test())


def test_search_documents_filters_by_type(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "search_documents", {"doc_type": "invoice"}
            )
            payload = json.loads(result.content[0].text)
            assert payload["total_results"] == 1
            assert payload["results"][0]["canonical_name"].startswith(
                "2024-01-15_invoice"
            )

    _run(_test())


def test_search_documents_filters_by_vendor(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "search_documents", {"vendor": "stadtwerke"}
            )
            payload = json.loads(result.content[0].text)
            assert payload["total_results"] == 1

    _run(_test())


def test_search_documents_no_match_returns_empty(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "search_documents", {"doc_type": "contract"}
            )
            payload = json.loads(result.content[0].text)
            assert payload["total_results"] == 0

    _run(_test())


def test_read_document_returns_text(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "read_document",
                {"name": "2024-01-15_invoice_acme_INV-1.pdf"},
            )
            payload = json.loads(result.content[0].text)
            assert payload["vendor"] == "Acme Corp"
            assert "consulting" in payload["extracted_text"]
            assert payload["text_truncated"] is False

    _run(_test())


def test_read_document_truncates_on_max_chars(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "read_document",
                {"name": "2024-01-15_invoice_acme_INV-1.pdf", "max_chars": 5},
            )
            payload = json.loads(result.content[0].text)
            assert payload["text_truncated"] is True
            assert len(payload["extracted_text"]) == 5

    _run(_test())


def test_read_document_missing_returns_error(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "read_document",
                {"name": "no-such-file.pdf"},
            )
            payload = json.loads(result.content[0].text)
            assert "error" in payload

    _run(_test())


def test_grep_documents_finds_match(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "grep_documents",
                {"pattern": r"Kundennummer \d+"},
            )
            payload = json.loads(result.content[0].text)
            assert payload["match_count"] == 1
            assert payload["matches"][0]["document"].startswith("2024-06-10_bill")

    _run(_test())


def test_grep_documents_case_insensitive_by_default(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "grep_documents",
                {"pattern": "acme"},
            )
            payload = json.loads(result.content[0].text)
            assert payload["match_count"] >= 1

    _run(_test())


def test_grep_documents_invalid_regex_returns_error(server: FastMCP) -> None:
    async def _test() -> None:
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool(
                "grep_documents",
                {"pattern": "[unclosed"},
            )
            payload = json.loads(result.content[0].text)
            assert "error" in payload

    _run(_test())


def test_empty_library_list_returns_zero(tmp_path: Path) -> None:
    empty_lib = tmp_path / "empty"
    empty_lib.mkdir()
    empty_server = create_server(empty_lib)

    async def _test() -> None:
        async with create_connected_server_and_client_session(empty_server) as session:
            result = await session.call_tool("list_documents", {})
            payload = json.loads(result.content[0].text)
            assert payload["total_results"] == 0

    _run(_test())
