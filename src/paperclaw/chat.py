from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from paperclaw._tools import TOOL_SCHEMAS, execute_tool
from paperclaw.library_index import LibraryIndex, render_metadata_table

logger = logging.getLogger(__name__)

# Rough char/token ratio for English+structured text. Used as a heuristic only;
# the API's reported usage is authoritative.
CHARS_PER_TOKEN = 4
# Sonnet 4.6 and Opus 4.6/4.7 expose 1M-token windows. We treat 30% of that as
# the maximum share for the inline metadata index, leaving headroom for tool
# results, conversation, and the model's response.
DEFAULT_CONTEXT_WINDOW = 1_000_000
MAX_INLINE_METADATA_RATIO = 0.30
MAX_AGENT_ITERATIONS = 12
MAX_OUTPUT_TOKENS = 8192

_SYSTEM_PREAMBLE = """\
You are PaperClaw's chat assistant. The user maintains a local library of \
PDFs that have been classified and given Markdown sidecars containing \
metadata and extracted text. Your job is to answer questions about that \
library by calling the tools provided.

Conventions:
- Every document is identified by its canonical filename: \
`YYYY-MM-DD_<type>_<vendor>_<reference>.pdf` (fields may be unknown).
- Document types: invoice, bill, contract, bank_statement, tax, insurance, \
letter, other.
- Dates are ISO YYYY-MM-DD. Amounts are stored as `<value> <currency>` \
strings (e.g. `99.0 EUR`).
- When uncertain about a name, call `search_documents` or `list_documents` \
before `read_document`. Use `grep_documents` to locate identifiers, \
amounts, or phrases.
- Cite the canonical filename for any document you reference. Be concise."""


class ChatSession:
    """A REPL-driven Claude session over a paperclaw library."""

    def __init__(
        self,
        *,
        index: LibraryIndex,
        api_key: str,
        model: str,
        inline_metadata: bool = True,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
    ) -> None:
        self._index = index
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._context_window = context_window
        self._messages: list[dict[str, Any]] = []
        self._metadata_inlined = False
        self._system_blocks = self._build_system(inline_metadata)
        self._last_usage: anthropic.types.Usage | None = None
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cache_read = 0
        self._total_cache_write = 0

    @property
    def messages(self) -> list[dict[str, Any]]:
        return self._messages

    @property
    def usage_summary(self) -> dict[str, int]:
        return {
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "cache_read_input_tokens": self._total_cache_read,
            "cache_creation_input_tokens": self._total_cache_write,
        }

    def metadata_inlined(self) -> bool:
        return self._metadata_inlined

    def ask(self, user_message: str) -> str:
        """Send a user turn, run the agentic loop, return the final text."""
        self._messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_AGENT_ITERATIONS):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=self._system_blocks,
                tools=TOOL_SCHEMAS,
                messages=self._messages,
            )
            self._record_usage(response.usage)

            self._messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                return _extract_text(response.content)
            if response.stop_reason == "tool_use":
                tool_results = self._run_tool_calls(response.content)
                self._messages.append({"role": "user", "content": tool_results})
                continue
            if response.stop_reason == "max_tokens":
                return (
                    _extract_text(response.content)
                    + "\n\n[Response truncated at max_tokens.]"
                )
            # refusal or anything unexpected — surface what we have
            return _extract_text(response.content) or (
                f"[Stopped with stop_reason={response.stop_reason!r}.]"
            )

        return "[Agent loop exceeded maximum iterations.]"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_system(self, inline_metadata: bool) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = [{"type": "text", "text": _SYSTEM_PREAMBLE}]

        if not inline_metadata or len(self._index) == 0:
            note = (
                f"The library at `{self._index.root}` currently contains "
                f"{len(self._index)} document(s). Use `list_documents` to enumerate."
            )
            blocks.append({"type": "text", "text": note})
        else:
            table = render_metadata_table(self._index)
            estimated_tokens = len(table) // CHARS_PER_TOKEN
            budget = int(self._context_window * MAX_INLINE_METADATA_RATIO)
            if estimated_tokens <= budget:
                inline = (
                    f"The library at `{self._index.root}` contains "
                    f"{len(self._index)} document(s). Full metadata index below — "
                    "use it to pick documents directly, then call `read_document` "
                    "for full text:\n\n"
                    f"```\n{table}\n```"
                )
                blocks.append({"type": "text", "text": inline})
                self._metadata_inlined = True
            else:
                note = (
                    f"The library at `{self._index.root}` contains "
                    f"{len(self._index)} document(s). The metadata index is too "
                    f"large to inline (~{estimated_tokens} tokens > "
                    f"{budget} budget). Use `list_documents` / "
                    "`search_documents` for paginated access."
                )
                blocks.append({"type": "text", "text": note})

        # Cache the full prefix (tools + system). One breakpoint, marked on the
        # last system block — caches everything before it.
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
        return blocks

    def _run_tool_calls(self, content: list[Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for block in content:
            if getattr(block, "type", None) != "tool_use":
                continue
            try:
                output = execute_tool(block.name, dict(block.input), self._index)
                is_error = False
            except Exception as exc:  # noqa: BLE001
                logger.exception("tool %s failed", block.name)
                output = json.dumps({"error": f"{type(exc).__name__}: {exc}"})
                is_error = True
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                    "is_error": is_error,
                }
            )
        return results

    def _record_usage(self, usage: anthropic.types.Usage | None) -> None:
        if usage is None:
            return
        self._last_usage = usage
        self._total_input_tokens += usage.input_tokens or 0
        self._total_output_tokens += usage.output_tokens or 0
        self._total_cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
        self._total_cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0


def _extract_text(content: list[Any]) -> str:
    parts = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()
