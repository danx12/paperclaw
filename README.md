# PaperClaw

A document-management CLI that classifies PDFs, renames them with a canonical convention, and writes Markdown transcript sidecars that an agent can search.

## How it works

```
~/inbox/*.pdf
    → extract text (pdfplumber)
    → if API key set: Claude classifies + extracts metadata (date, vendor, amount, ref)
    → if no API key: local rules classify (filename regex + content keywords)
    → confidence ≥ 0.50 (Claude) or ≥ 0.75 (local) → ~/library/YYYY-MM-DD_type_vendor_ref.pdf
    → low confidence or image-only → ~/library/_unsorted/
```

Each stored PDF gets a `.md` sidecar with structured metadata and the full extracted text, making the library grep-able and semantically searchable.

The CLI exposes two commands:

| Command | What it does |
|---|---|
| `paperclaw ingest` | Run the classification pipeline over an inbox. |
| `paperclaw chat`   | Open a chat REPL that can search, filter, read, and grep the library via Claude tool use. |

## Installation

```bash
# With pixi (recommended)
pixi install

# Or directly
pip install -e .
```

## Quick start

```bash
# 1. Scaffold a demo inbox with the bundled test PDFs
pixi run demo
# → Inbox ready: /tmp/paperclaw-demo/inbox
# → Library:     /tmp/paperclaw-demo/library

# 2. Run with an Anthropic key — Claude extracts full metadata
ANTHROPIC_API_KEY=sk-... paperclaw ingest --inbox /tmp/paperclaw-demo/inbox --library /tmp/paperclaw-demo/library
# → Found 2 PDF(s) in /tmp/paperclaw-demo/inbox. [Claude (claude-haiku-4-5-20251001)]
# → [1/2] finanzamt-bescheid.pdf ...      stored → 2026-04-28_tax_finanzamt-m-nchen_V-EKST-2025.pdf
# → [2/2] stadtwerke-stromrechnung.pdf ... stored → 2026-04-12_bill_stadtwerke-m-nchen-gmbh_R-118442.pdf

# Without a key, local rules classify type only (vendor/date stay unknown)
paperclaw ingest --inbox /tmp/paperclaw-demo/inbox --library /tmp/paperclaw-demo/library
# → Found 2 PDF(s) in /tmp/paperclaw-demo/inbox. [local rules only]
# → [1/2] finanzamt-bescheid.pdf ...      stored → 0000-00-00_tax_unknown_noref.pdf
# → [2/2] stadtwerke-stromrechnung.pdf ... stored → 0000-00-00_bill_unknown_noref.pdf

# 3. Chat with the resulting library
paperclaw chat --library /tmp/paperclaw-demo/library
# → PaperClaw chat [claude-sonnet-4-6] over /tmp/paperclaw-demo/library — 2 document(s), metadata inlined.
# → Type your question, or /usage, /quit.
# you> What's my electricity bill total?
# claude> Your Stadtwerke München bill (R-118442) totals 47.83 EUR.
```

Re-run `pixi run demo` to reset the inbox before each trial (PDFs are moved, not copied).

## Configuration

Settings resolve in priority order: **CLI flag > env var > config file > default**.

| Parameter | CLI flag | Env var | Default |
|---|---|---|---|
| API key | `--api-key` | `ANTHROPIC_API_KEY` | *(optional)* |
| Classify model | `--model` | `PAPERCLAW_MODEL` | `claude-haiku-4-5-20251001` |
| Chat model | `--chat-model` | `PAPERCLAW_CHAT_MODEL` | `claude-sonnet-4-6` |
| Local threshold | `--threshold` | `PAPERCLAW_THRESHOLD` | `0.75` |
| Claude min confidence | `--claude-min` | `PAPERCLAW_CLAUDE_MIN` | `0.50` |
| Inbox | `--inbox` | `PAPERCLAW_INBOX` | `~/inbox` |
| Library | `--library` | `PAPERCLAW_LIBRARY` | `~/library` |
| Config file | `--config` | `PAPERCLAW_CONFIG` | `~/.config/paperclaw/config.toml` |

**Example `~/.config/paperclaw/config.toml`:**

```toml
model = "claude-haiku-4-5-20251001"
chat_model = "claude-sonnet-4-6"
threshold = 0.75
claude_min = 0.50
inbox = "/Users/me/Documents/scans"
library = "/Users/me/Documents/library"
# api_key = "..."   # prefer the env var
```

## Output format

### Canonical filename

Classified PDFs land in `~/library/` under a four-part name:

```
YYYY-MM-DD _ <type> _ <vendor-slug> _ <ref-slug> .pdf
```

Each part is separated by `_`. The vendor and reference segments are **slugified**:
- lowercased
- runs of non-alphanumeric characters replaced by `-`
- leading/trailing `-` trimmed
- truncated to 40 characters

**Fallback values when a field is missing:**

| Field | Fallback |
|---|---|
| date | `0000-00-00` |
| vendor | `unknown` |
| reference | `noref` |

**Document types:** `invoice`, `bill`, `contract`, `bank_statement`, `tax`, `insurance`, `letter`, `other`

**Examples:**

| Scenario | Filename |
|---|---|
| Full metadata | `2024-11-01_invoice_acme-gmbh_INV-9912.pdf` |
| No date | `0000-00-00_invoice_acme-gmbh_INV-9912.pdf` |
| No reference | `2025-03-15_bill_vattenfall_noref.pdf` |
| No vendor | `2025-01-10_tax_unknown_noref.pdf` |
| Low confidence / image-only | `_unsorted/original-name_a1b2c3d4.pdf` |

**Collision handling.** If the target filename already exists, an 8-character SHA-256 content hash of the source file is appended:

```
2024-11-01_invoice_acme-gmbh_INV-9912_a1b2c3d4.pdf
```

Because the hash is derived from file content, re-running the same inbox is idempotent — the same file always maps to the same output name.

**Unsorted files** (`_unsorted/`) always include the hash (no collision check needed):

```
_unsorted/<original-stem>_<hash8>.pdf
```

### Sidecar

A `.md` sidecar with the same stem is written alongside every PDF:

```markdown
# 2024-11-01_invoice_acme-gmbh_INV-9912.pdf

**Source**: original-inbox-name.pdf
**Extracted**: 2024-11-02T09:14:33Z
**PaperClaw**: 0.1.0
**Type**: invoice
**Date**: 2024-11-01
**Vendor**: Acme GmbH
**Amount**: 99.0 EUR
**Reference**: INV-9912
**Confidence**: 90%

## Extracted Text

[full pdfplumber output]
```

> **Privacy note.** Sidecars contain the full extracted text. Treat `~/library/` as sensitive storage — bank statements and tax documents are grep-able on disk.

## Chat

`paperclaw chat` opens an interactive REPL over a library. Claude has tool access to four search primitives and a context-aware metadata index built from the `.md` sidecars.

```bash
# Interactive REPL
paperclaw chat --library /tmp/paperclaw-demo/library

# One-shot — useful for scripting
paperclaw chat --library /tmp/paperclaw-demo/library --ask "Which invoices are above 50 EUR?"
```

**REPL commands**

| Input | Effect |
|---|---|
| `<your question>` | Send a turn; Claude may invoke tools before replying. |
| `/usage` | Print cumulative token usage (input, output, cache read, cache write). |
| `/quit` (or `/exit`, `:q`, `Ctrl-D`) | End the session. |

**Tools exposed to the model**

| Tool | Purpose |
|---|---|
| `list_documents(page, page_size, sort_by)` | Paginated metadata listing. Sort by `date_desc` (default), `date_asc`, or `name`. |
| `search_documents(doc_type, vendor, date_from, date_to, text, page, page_size)` | Filter by structured fields and/or substring; results paginated. |
| `read_document(name, max_chars=12000)` | Full sidecar (metadata + extracted text) for one canonical filename. Returns `text_truncated` and `full_text_chars` so the model can request more. |
| `grep_documents(pattern, case_sensitive=false, max_matches=50)` | Regex search across every sidecar body; returns `{document, line, snippet}` rows. |

**Context-window strategy.** Each session estimates the size of the full metadata index (a `name | date | type | vendor | reference | amount` table). If it fits under **30%** of the chat model's context window (~300K tokens at Sonnet 4.6's 1M ceiling), it is inlined directly in the system prompt — Claude can answer "what do I have" questions without any tool calls. If it doesn't fit, the system prompt simply notes the document count and Claude must paginate via `list_documents` / `search_documents`. Force pagination at any size with `--no-inline-metadata`.

**Prompt caching.** Tools and the system prompt (including the inlined metadata index, when present) are marked with a single `cache_control` breakpoint on the last system block. After the first turn the entire prefix serves from cache at ~0.1× cost. `/usage` reports `cache_read` vs `cache_write` so you can verify hits.

**Privacy reminder.** The chat request sends the full inlined metadata table (and any tool result the model fetches) to Anthropic. If the library contains tax or banking documents, treat that the same way you treat ingest classification — see the privacy note under [Output format → Sidecar](#sidecar).

## Classifier decision logic

| Signal | Confidence | Action |
|---|---|---|
| Filename regex hit | 0.85 | Store directly |
| Content keyword hit | 0.60 | Store directly |
| Neither | 0.30 | Escalate to Claude |
| Empty text (image-only) | 0.00 | `_unsorted/`, skip Claude |

Local patterns cover German and English document keywords (`rechnung`, `invoice`, `kontoauszug`, `statement`, `finanzamt`, `tax`, …).

## Development

```bash
# Install dev environment
pixi install

# Run tests (non-integration, fast)
pixi run test

# Run all tests including integration
pixi run pytest -m "integration or not integration"

# Lint
pixi run lint

# Format
pixi run fmt
```

Tests use real sample PDFs in `tests/data/` and mock the Anthropic API — no key needed to run the suite.
