from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

app = typer.Typer(
    help="Turn a folder of PDFs into an organized, agent-searchable library."
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


@app.command()
def main(
    inbox: Annotated[
        Path | None, typer.Option(help="Directory scanned for *.pdf.")
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
    """Process all PDFs in the inbox and store them in the library."""
    load_dotenv()

    from paperclaw._config import load_settings
    from paperclaw.classifier import ClaudeClassifier, LocalRulesClassifier
    from paperclaw.extractor import PdfPlumberExtractor
    from paperclaw.pipeline import Pipeline
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

    pdfs = sorted(settings.inbox.glob("*.pdf"))
    n = len(pdfs)

    if not pdfs:
        typer.echo(f"No PDF files found in {settings.inbox}.")
        return

    key_status = f"Claude ({settings.model})" if claude_clf else "local rules only"
    typer.echo(f"Found {n} PDF(s) in {settings.inbox}. [{key_status}]\n")

    results = []
    for i, pdf in enumerate(pdfs, 1):
        typer.echo(f"[{i}/{n}] {pdf.name} ... ", nl=False)
        try:
            doc = pipeline.process_file(pdf)
            results.append(doc)
            in_unsorted = "_unsorted" in str(doc.library_path)
            if in_unsorted:
                typer.secho(f"unsorted → {doc.canonical_name}", fg=typer.colors.YELLOW)
            else:
                typer.secho(f"stored   → {doc.canonical_name}", fg=typer.colors.GREEN)
        except Exception as exc:
            typer.secho(f"ERROR: {exc}", fg=typer.colors.RED, err=True)

    typer.echo(f"\nDone. {len(results)}/{n} file(s) processed → {settings.library}")
