from __future__ import annotations

import copy
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from paperclaw import chat as chat_module
from paperclaw.chat import ChatSession
from paperclaw.library_index import LibraryIndex

SIDECAR = """\
# 2024-01-15_invoice_acme_INV-1.pdf

**Type**: invoice
**Date**: 2024-01-15
**Vendor**: Acme
**Amount**: 100.0 EUR
**Reference**: INV-1
**Confidence**: 90%

## Extracted Text

Acme invoice for widgets.
Total: 100.00 EUR
"""


@dataclass
class FakeBlock:
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 20
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class FakeResponse:
    content: list[FakeBlock]
    stop_reason: str
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeMessages:
    def __init__(self, scripted: list[FakeResponse]) -> None:
        self._scripted = list(scripted)
        self.create_calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        # Snapshot mutable inputs so later mutation in the caller doesn't
        # rewrite what we recorded.
        self.create_calls.append({k: copy.deepcopy(v) for k, v in kwargs.items()})
        if not self._scripted:
            raise AssertionError("FakeMessages: no more scripted responses")
        return self._scripted.pop(0)


class FakeAnthropic:
    def __init__(self, scripted: list[FakeResponse]) -> None:
        self.messages = FakeMessages(scripted)


@pytest.fixture
def index(tmp_path: Path) -> LibraryIndex:
    lib = tmp_path / "library"
    lib.mkdir()
    (lib / "2024-01-15_invoice_acme_INV-1.md").write_text(SIDECAR, encoding="utf-8")
    return LibraryIndex.load(lib)


@pytest.fixture
def patched_client(monkeypatch: pytest.MonkeyPatch):
    """Replace anthropic.Anthropic with a constructor that returns a scripted fake."""

    holder: dict[str, FakeAnthropic] = {}

    def factory(scripted: list[FakeResponse]) -> None:
        fake = FakeAnthropic(scripted)

        class FakeAnthropicCls:
            def __init__(self, *_a: Any, **_kw: Any) -> None:
                pass

            messages = fake.messages

        monkeypatch.setattr(chat_module.anthropic, "Anthropic", FakeAnthropicCls)
        holder["fake"] = fake

    yield factory, holder


def test_session_inlines_metadata_for_small_library(index: LibraryIndex) -> None:
    # Use a dummy client; ChatSession.__init__ only constructs the client, no call.
    chat_module.anthropic.Anthropic = lambda **_kw: types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **_k: None)
    )
    session = ChatSession(index=index, api_key="x", model="m", inline_metadata=True)
    assert session.metadata_inlined() is True


def test_session_skips_inline_when_disabled(index: LibraryIndex) -> None:
    chat_module.anthropic.Anthropic = lambda **_kw: types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **_k: None)
    )
    session = ChatSession(index=index, api_key="x", model="m", inline_metadata=False)
    assert session.metadata_inlined() is False


def test_ask_dispatches_tool_call_then_stops(
    index: LibraryIndex, patched_client
) -> None:
    factory, holder = patched_client
    factory(
        [
            FakeResponse(
                content=[
                    FakeBlock(
                        type="tool_use",
                        id="t1",
                        name="search_documents",
                        input={"doc_type": "invoice"},
                    )
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(
                content=[FakeBlock(type="text", text="You have 1 invoice from Acme.")],
                stop_reason="end_turn",
            ),
        ]
    )

    session = ChatSession(index=index, api_key="x", model="claude-sonnet-4-6")
    reply = session.ask("How many invoices?")

    assert reply == "You have 1 invoice from Acme."

    fake = holder["fake"]
    assert len(fake.messages.create_calls) == 2

    # The second call's messages should contain the tool_result for t1.
    second_messages = fake.messages.create_calls[1]["messages"]
    tool_result_msg = second_messages[-1]
    assert tool_result_msg["role"] == "user"
    assert tool_result_msg["content"][0]["type"] == "tool_result"
    assert tool_result_msg["content"][0]["tool_use_id"] == "t1"


def test_ask_handles_tool_error_gracefully(index: LibraryIndex, patched_client) -> None:
    factory, holder = patched_client
    factory(
        [
            FakeResponse(
                content=[
                    FakeBlock(
                        type="tool_use",
                        id="t1",
                        name="grep_documents",
                        input={"pattern": "[unclosed"},
                    )
                ],
                stop_reason="tool_use",
            ),
            FakeResponse(
                content=[FakeBlock(type="text", text="Couldn't run that regex.")],
                stop_reason="end_turn",
            ),
        ]
    )
    session = ChatSession(index=index, api_key="x", model="m")
    reply = session.ask("grep for [unclosed")
    assert "Couldn't" in reply

    # Tool result was passed back as is_error=False (the tool reported the
    # error inside its JSON body) — the dispatcher does not raise.
    second = holder["fake"].messages.create_calls[1]["messages"][-1]
    assert second["content"][0]["type"] == "tool_result"


def test_usage_summary_aggregates(index: LibraryIndex, patched_client) -> None:
    factory, holder = patched_client
    factory(
        [
            FakeResponse(
                content=[FakeBlock(type="text", text="hi")],
                stop_reason="end_turn",
                usage=FakeUsage(
                    input_tokens=10,
                    output_tokens=2,
                    cache_read_input_tokens=5,
                    cache_creation_input_tokens=3,
                ),
            )
        ]
    )
    session = ChatSession(index=index, api_key="x", model="m")
    session.ask("hi")
    summary = session.usage_summary
    assert summary == {
        "input_tokens": 10,
        "output_tokens": 2,
        "cache_read_input_tokens": 5,
        "cache_creation_input_tokens": 3,
    }
