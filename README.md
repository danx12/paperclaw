# PaperClaw

A document-management CLI that classifies PDFs, renames them with a canonical convention, and writes Markdown transcript sidecars that an agent can search.

## How it works

```
~/inbox/*.pdf
    → extract text (pdfplumber)
    → local rules classify (filename regex + content keywords)
    → if confidence ≥ 0.75: store as YYYY-MM-DD_type_vendor_ref.pdf
    → if confidence < 0.75 and API key set: Claude classifies
    → low-confidence or image-only → ~/library/_unsorted/
```

Each stored PDF gets a `.md` sidecar with structured metadata and the full extracted text, making the library grep-able and semantically searchable.

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

# 2. Run PaperClaw on it (no API key needed — local rules handle everything)
paperclaw --inbox /tmp/paperclaw-demo/inbox --library /tmp/paperclaw-demo/library
# → Processed 2 file(s).
# →   0000-00-00_tax_unknown_noref.pdf
# →   0000-00-00_bill_unknown_noref.pdf

# Check the library
ls /tmp/paperclaw-demo/library/
cat "/tmp/paperclaw-demo/library/0000-00-00_bill_unknown_noref.md"
```

With an Anthropic key, low-confidence documents are escalated to Claude, which fills in date, vendor, amount, and reference:

```bash
ANTHROPIC_API_KEY=sk-... paperclaw --inbox ~/scans --library ~/library
```

Re-run `pixi run demo` to reset the inbox before each trial (PDFs are moved, not copied).

## Configuration

Settings resolve in priority order: **CLI flag > env var > config file > default**.

| Parameter | CLI flag | Env var | Default |
|---|---|---|---|
| API key | `--api-key` | `ANTHROPIC_API_KEY` | *(optional)* |
| Model | `--model` | `PAPERCLAW_MODEL` | `claude-sonnet-4-6` |
| Local threshold | `--threshold` | `PAPERCLAW_THRESHOLD` | `0.75` |
| Claude min confidence | `--claude-min` | `PAPERCLAW_CLAUDE_MIN` | `0.50` |
| Inbox | `--inbox` | `PAPERCLAW_INBOX` | `~/inbox` |
| Library | `--library` | `PAPERCLAW_LIBRARY` | `~/library` |
| Config file | `--config` | `PAPERCLAW_CONFIG` | `~/.config/paperclaw/config.toml` |

**Example `~/.config/paperclaw/config.toml`:**

```toml
model = "claude-sonnet-4-6"
threshold = 0.75
claude_min = 0.50
inbox = "/Users/me/Documents/scans"
library = "/Users/me/Documents/library"
# api_key = "..."   # prefer the env var
```

## Output format

Classified PDFs land in `~/library/` under a canonical name:

```
YYYY-MM-DD_type_vendor-slug_ref-slug.pdf
```

| Scenario | Example |
|---|---|
| Full metadata | `2024-11-01_invoice_acme-gmbh_INV-9912.pdf` |
| No date | `0000-00-00_invoice_acme-gmbh_INV-9912.pdf` |
| No reference | `2025-03-15_bill_vattenfall_noref.pdf` |
| Low confidence / image-only | `_unsorted/original-name_a1b2c3d4.pdf` |

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
