from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from paperclaw.cli import app

runner = CliRunner()
DATA_DIR = Path(__file__).parent / "data"


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "inbox" in result.output.lower()


def test_empty_inbox(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    library = tmp_path / "library"

    result = runner.invoke(app, ["--inbox", str(inbox), "--library", str(library)])

    assert result.exit_code == 0
    assert "No PDF" in result.output


def test_run_with_pdf(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    shutil.copy(
        DATA_DIR / "stadtwerke-stromrechnung.pdf",
        inbox / "stadtwerke-stromrechnung.pdf",
    )
    library = tmp_path / "library"

    result = runner.invoke(app, ["--inbox", str(inbox), "--library", str(library)])

    assert result.exit_code == 0
    assert "1 file" in result.output


def test_config_file_loaded(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    library = tmp_path / "library"
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'inbox = "{inbox}"\nlibrary = "{library}"\n', encoding="utf-8")

    result = runner.invoke(app, ["--config", str(cfg)])

    assert result.exit_code == 0


def test_cli_flag_overrides_config(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    library = tmp_path / "library"
    cfg = tmp_path / "config.toml"
    other_inbox = tmp_path / "other_inbox"
    other_inbox.mkdir()
    cfg.write_text(
        f'inbox = "{other_inbox}"\nlibrary = "{library}"\n', encoding="utf-8"
    )

    result = runner.invoke(app, ["--config", str(cfg), "--inbox", str(inbox)])

    assert result.exit_code == 0
    assert "No PDF" in result.output
