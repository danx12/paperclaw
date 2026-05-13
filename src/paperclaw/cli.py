from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

app = typer.Typer(
    help="Turn a folder of PDFs into an organized, agent-searchable library.",
    no_args_is_help=True,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


@app.command("ingest")
def ingest(
    inbox: Annotated[
        Path | None, typer.Option(help="Directory scanned for *.pdf and *.png.")
    ] = None,
    library: Annotated[
        Path | None, typer.Option(help="Destination root; _unsorted/ lives inside it.")
    ] = None,
    threshold: Annotated[
        float | None,
        typer.Option(help="Local-rules confidence threshold (no-key fallback)."),
    ] = None,
    claude_min: Annotated[
        float | None,
        typer.Option(help="Claude confidence below which result routes to _unsorted/."),
    ] = None,
    model: Annotated[
        str | None, typer.Option(help="Claude model ID for classification.")
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option(help="Anthropic API key (prefer ANTHROPIC_API_KEY env var)."),
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Path to a TOML config file.")
    ] = None,
) -> None:
    """Process all PDFs and PNGs in the inbox and store them in the library."""
    load_dotenv()

    from paperclaw._config import load_settings
    from paperclaw.classifier import ClaudeClassifier, LocalRulesClassifier
    from paperclaw.extractor import PdfPlumberExtractor
    from paperclaw.pipeline import Pipeline, iter_inputs
    from paperclaw.storage import FilesystemStorer

    settings = load_settings(
        config_path=config,
        inbox=inbox,
        library=library,
        threshold=threshold,
        claude_min=claude_min,
        model=model,
        api_key=api_key,
    )

    extractor = PdfPlumberExtractor()
    local_clf = LocalRulesClassifier()
    claude_clf: ClaudeClassifier | None = (
        ClaudeClassifier(api_key=settings.api_key, model=settings.model)
        if settings.api_key
        else None
    )
    storer = FilesystemStorer(settings.library)

    pipeline = Pipeline(
        extractor=extractor,
        local_classifier=local_clf,
        storer=storer,
        claude_classifier=claude_clf,
        threshold=settings.threshold,
        claude_min=settings.claude_min,
    )

    inputs = iter_inputs(settings.inbox)
    n = len(inputs)

    if not inputs:
        typer.echo(f"No PDF or PNG files found in {settings.inbox}.")
        return

    key_status = f"Claude ({settings.model})" if claude_clf else "local rules only"
    typer.echo(f"Found {n} file(s) in {settings.inbox}. [{key_status}]\n")

    results = []
    for i, path in enumerate(inputs, 1):
        typer.echo(f"[{i}/{n}] {path.name} ... ", nl=False)
        try:
            doc = pipeline.process_file(path)
            results.append(doc)
            in_unsorted = "_unsorted" in str(doc.library_path)
            if in_unsorted:
                typer.secho(f"unsorted → {doc.canonical_name}", fg=typer.colors.YELLOW)
            else:
                typer.secho(f"stored   → {doc.canonical_name}", fg=typer.colors.GREEN)
        except Exception as exc:
            typer.secho(f"ERROR: {exc}", fg=typer.colors.RED, err=True)

    typer.echo(f"\nDone. {len(results)}/{n} file(s) processed → {settings.library}")


@app.command("chat")
def chat(
    library: Annotated[
        Path | None,
        typer.Option(help="Library root containing classified PDFs and sidecars."),
    ] = None,
    chat_model: Annotated[
        str | None,
        typer.Option(help="Claude model ID for chat (separate from --model)."),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option(help="Anthropic API key (prefer ANTHROPIC_API_KEY env var)."),
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Path to a TOML config file.")
    ] = None,
    no_inline_metadata: Annotated[
        bool,
        typer.Option(
            "--no-inline-metadata",
            help="Always paginate via tools, even when the metadata index would fit.",
        ),
    ] = False,
    question: Annotated[
        str | None,
        typer.Option(
            "--ask",
            help="Ask one question and exit, instead of starting the REPL.",
        ),
    ] = None,
) -> None:
    """Chat with your library. Loads sidecar metadata and exposes 4 search tools."""
    load_dotenv()

    from paperclaw._config import load_settings
    from paperclaw.chat import ChatSession
    from paperclaw.library_index import LibraryIndex

    settings = load_settings(
        config_path=config,
        library=library,
        api_key=api_key,
        chat_model=chat_model,
    )
    if not settings.api_key:
        typer.secho(
            "Chat requires an Anthropic API key (set ANTHROPIC_API_KEY or --api-key).",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    if not settings.library.exists():
        typer.secho(
            f"Library directory {settings.library} does not exist.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    index = LibraryIndex.load(settings.library)
    if len(index) == 0:
        typer.secho(
            f"No sidecars found under {settings.library}. "
            "Run `paperclaw ingest` first to populate the library.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=1)

    session = ChatSession(
        index=index,
        api_key=settings.api_key,
        model=settings.chat_model,
        inline_metadata=not no_inline_metadata,
    )

    inline_state = "inlined" if session.metadata_inlined() else "paginated via tools"
    typer.secho(
        f"PaperClaw chat [{settings.chat_model}] over {settings.library} "
        f"— {len(index)} document(s), metadata {inline_state}.",
        fg=typer.colors.GREEN,
    )

    if question is not None:
        reply = session.ask(question)
        typer.echo(reply)
        _print_usage(session)
        return

    typer.echo("Type your question, or /usage, /quit.\n")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo()
            break
        if not line:
            continue
        if line in ("/quit", "/exit", ":q"):
            break
        if line == "/usage":
            _print_usage(session)
            continue
        try:
            reply = session.ask(line)
        except Exception as exc:  # noqa: BLE001
            typer.secho(f"ERROR: {exc}", fg=typer.colors.RED, err=True)
            continue
        typer.secho(f"\nclaude> {reply}\n", fg=typer.colors.CYAN)


@app.command("mcp")
def mcp_serve(
    library: Annotated[
        Path | None,
        typer.Option(help="Library root containing classified PDFs and sidecars."),
    ] = None,
    config: Annotated[
        Path | None, typer.Option(help="Path to a TOML config file.")
    ] = None,
) -> None:
    """Start an MCP server over stdio (for Claude Desktop, claude.ai/code, etc.)."""
    load_dotenv()

    from paperclaw._config import load_settings
    from paperclaw.mcp_server import run_stdio

    settings = load_settings(config_path=config, library=library)

    if not settings.library.exists():
        typer.secho(
            f"Library directory {settings.library} does not exist.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    typer.secho(
        f"PaperClaw MCP server starting for {settings.library} …",
        fg=typer.colors.GREEN,
        err=True,
    )
    run_stdio(settings.library)


def _print_usage(session: object) -> None:
    summary = session.usage_summary  # type: ignore[attr-defined]
    typer.echo(
        f"[usage] input={summary['input_tokens']} "
        f"output={summary['output_tokens']} "
        f"cache_read={summary['cache_read_input_tokens']} "
        f"cache_write={summary['cache_creation_input_tokens']}"
    )
