# 🌴 PaperClaw — Best Agentic Engineering Vibe Check

## 🪩 TL;DR
- **Score:** 50 / 100 — *Works for now. Drink some water before the agent gets ambitious.*
- **Biggest win:** Schemas + I/O separation — pydantic-frozen models plus Protocol seams (`Extractor`/`Classifier`/`Storer`) make every step testable without mocks of the world.
- **Biggest miss:** No `AGENTS.md` / `CLAUDE.md` — a fresh agent has to derive everything from `README.md` and `pixi.toml`.
- **Do this now:** Create `AGENTS.md` with the four lines an agent needs: install (`pixi install`), test (`pixi run test`), lint+fmt (`pixi run lint && pixi run fmt`), and the demo entrypoint (`pixi run demo` → `paperclaw --inbox … --library …`).
- **Earned bonuses:** 2 🎁🎁 — *Vibe Pioneer*

## 🌴 Stack detected
- **Language:** Python 3.12
- **Package manager:** pixi (conda-forge) with editable PyPI install
- **Toolchain notes:** ruff · black · pytest · pytest-cov · prek (pre-commit) · pydantic v2 · typer · pdfplumber · anthropic SDK

## Vibe Check Report Card

┌─────┬──────────────────────────────────────┬──────┬───────────────────────────────────────────────────────────────────────────────────────────────┐
│  #  │                Item                  │ Vibe │                                          Evidence                                             │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│  1  │ AGENTS.md / CLAUDE.md                │ 💀   │ Neither file exists at repo root. Only `.claude/skills/python-coding.md` (a skill, not agent  │
│     │                                      │      │ context). Fix: add `AGENTS.md` with run/test/lint commands and the demo path.                 │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│  2  │ Strict types / compiler              │ 🩹   │ `pyproject.toml` has no `[tool.mypy]` or `[tool.pyright]` block; ruff `ANN` enforces          │
│     │                                      │      │ annotations but no static type checker runs. Fix: add `mypy --strict src/` to `pixi run       │
│     │                                      │      │ check` and the pre-commit config.                                                             │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│  3  │ Strict linter / formatter            │ 🚀   │ `pyproject.toml:30` selects `E,W,F,I,UP,B,SIM,ANN` — broad, not the starter set. Black wired  │
│     │                                      │      │ alongside; both enforced via `.pre-commit-config.yaml:10–20`.                                 │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│  4  │ Schema validation at boundaries      │ 🚀   │ `src/paperclaw/schemas.py` defines `RawDocument`, `ClassifiedDocument`, `LibraryDocument` as  │
│     │                                      │      │ frozen pydantic BaseModels with `Field(ge=…, le=…, max_length=…)` and a `@model_validator`.  │
│     │                                      │      │ Claude responses parse through these same schemas.                                            │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│  5  │ Business logic separated from I/O    │ 🚀   │ `src/paperclaw/protocols.py` declares `Extractor`/`Classifier`/`Storer` Protocols.            │
│     │                                      │      │ `pipeline.py` is pure orchestration over those seams. `_naming.py` is pure functions.         │
│     │                                      │      │ `tests/test_pipeline.py` exercises the whole flow with in-memory fakes.                       │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│  6  │ One-command bring-up                 │ 🚀   │ `pixi install` (README:21) then uniform verbs: `pixi run test|lint|fmt|demo` (pixi.toml:22).  │
│     │                                      │      │ Single-package layout — no per-folder divergence.                                             │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│  7  │ Pre-commit feedback loop             │ 👍   │ `.pre-commit-config.yaml` runs ruff (autofix) + black + pytest non-integration + a custom     │
│     │                                      │      │ `.env` block. No gitleaks / detect-secrets — the `.env` filename pattern is the only secret   │
│     │                                      │      │ guard. CI runs `prek run --all-files` so config is genuinely exercised.                       │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│  8  │ Dead-code guardrail                  │ 🩹   │ Ruff `F` (selected at `pyproject.toml:30`) catches unused imports/locals, but no `vulture`    │
│     │                                      │      │ or `ruff` `RUF`/`PLR` for unused functions/classes. Fix: add `vulture src/` to `pixi run      │
│     │                                      │      │ lint`.                                                                                        │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│  9  │ Logs reachable from terminal         │ 👍   │ `logging.basicConfig(level=WARNING, …)` at `cli.py:14` plus `typer.echo` for status lines.    │
│     │                                      │      │ Everything streams to stdout/stderr. No dedicated `pixi run logs` script.                     │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│ 10  │ Docs stay in sync with code          │ 💀   │ `README.md` and `docs/DESIGN.md` exist but nothing flags code-only changes. No pre-commit     │
│     │                                      │      │ check, no CI rule, no generated reference. Fix: add a lefthook/prek hook that warns when      │
│     │                                      │      │ `src/**` changes without a `README.md`/`docs/**` touch.                                       │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│ 11  │ Agent can self-test end-to-end       │ 👍   │ `pixi run demo` (pixi.toml:26) scaffolds a real inbox/library with bundled PDFs; the CLI      │
│     │                                      │      │ prints status to stdout and writes inspectable `.md` sidecars. Discoverable from README       │
│     │                                      │      │ (would be 🚀 if pointed at from `AGENTS.md`).                                                 │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│ 12  │ Agentic review panel                 │ 💀   │ No `/review` slash command, no `REVIEW.md`, no script that spawns parallel specialist         │
│     │                                      │      │ reviewers. CI is pre-commit + integration tests only. Fix: add `.claude/commands/review.md`   │
│     │                                      │      │ that fans out to best-practices / python / security reviewers, plus a `REVIEW.md` ignore      │
│     │                                      │      │ list.                                                                                         │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│ 13  │ Friction proportional to blast       │ 💀   │ No `CODEOWNERS`, no danger-zone pre-push hook, no named bypass. `classifier.py` (Claude       │
│     │     radius                           │      │ prompt) and `_naming.py` (canonical filename — touches every stored doc) are blast-radius     │
│     │                                      │      │ surfaces with no extra friction. Fix: add a prek `local` hook that fails when                 │
│     │                                      │      │ `src/paperclaw/_naming.py` or `classifier.py` change without `PAPERCLAW_DANGER_OK=1`.         │
├─────┼──────────────────────────────────────┼──────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
│ 14  │ Tooling tuned for the agent          │ 🩹   │ The `no-env-files` hook prints a clear remediation message (.pre-commit-config.yaml:7).       │
│     │                                      │      │ The ruff/black/pytest hooks just exit non-zero with stock output — no "run `pixi run fmt`"   │
│     │                                      │      │ hint. No `.gitleaksignore`-style accept-list. Fix: wrap each hook's `entry` so it prints the  │
│     │                                      │      │ exact `pixi run …` command to fix on failure.                                                 │
└─────┴──────────────────────────────────────┴──────┴───────────────────────────────────────────────────────────────────────────────────────────────┘

## Category sub-scores

| Category | Items | Score | Badge |
|---|---|---|---|
| 🧱 Foundations | 2, 3, 4, 5 | 33 / 40 (82%) | 🛡️ **Type-Safe Citizen** — earned |
| ⚡ Feedback Loops | 6, 7, 8, 9, 14 | 30 / 50 (60%) | 🚦 Loop Closer — *locked* |
| 🤖 Agent Enablement | 1, 10, 11, 12 | 7 / 40 (17%) | 🔍 Agent-Ready — *locked* |
| 🚨 Blast-Radius Safety | 13 | 0 / 10 (0%) | 🛟 Blast-Radius Aware — *locked* |

## 🎁 Bonus finds

- 🎁 **`pixi run demo` bootstrap** (pixi.toml:26) — A single command resets `/tmp/paperclaw-demo`, copies the bundled test PDFs into a fresh inbox, and prints the exact `paperclaw …` command to run next. An agent can verify a real change end-to-end in one step.
- 🎁 **Protocol-based seams + frozen pydantic models** (`protocols.py`, `schemas.py`) — `Extractor`/`Classifier`/`Storer` are pure `typing.Protocol` interfaces, and every domain object is a frozen pydantic model with validators. The agent can swap in a fake classifier or storer in tests without touching the network or the filesystem, and refactors that violate the contract fail loudly.

Two genuine bonus finds → **Vibe Pioneer** sticker earned.

## 🎯 Vibe Score: 50 / 100

## 💊 Top 3 hangover preventions

1. **Add `AGENTS.md` at the repo root.** Four sections: how to install (`pixi install`), how to test (`pixi run test`), how to verify a change end-to-end (`pixi run demo` → `paperclaw …`), and the architectural seams the agent should respect (Protocols in `protocols.py`). This single file unlocks items 1, 10, and 11 in one move.
2. **Wire `mypy --strict` into `pixi run check` and pre-commit.** Ruff annotations are not a type checker. With pydantic models already everywhere, mypy strict will land almost clean.
3. **Add an agentic review entrypoint.** A `.claude/commands/review.md` that fans out to parallel python/security/best-practices reviewers, plus a short `REVIEW.md` that lists what *not* to flag (style nits already covered by ruff/black, theoretical risks in untouched code). Tier it by diff size so trivial fixes don't burn frontier tokens.

## 🪩 Verdict

**Works for now. Drink some water before the agent gets ambitious.** — and you've earned the *Vibe Pioneer* badge for the demo bootstrap + Protocol-seam pair. The foundations layer is genuinely ship-ready; the agent-enablement layer is where the next hour of work pays back the most.
