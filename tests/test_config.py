from __future__ import annotations

from pathlib import Path

import pytest

from paperclaw._config import Settings, load_settings

_PAPERCLAW_VARS = [
    "ANTHROPIC_API_KEY",
    "PAPERCLAW_MODEL",
    "PAPERCLAW_THRESHOLD",
    "PAPERCLAW_CLAUDE_MIN",
    "PAPERCLAW_INBOX",
    "PAPERCLAW_LIBRARY",
    "PAPERCLAW_CONFIG",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _PAPERCLAW_VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults() -> None:
    s = load_settings()
    assert s.model == "claude-haiku-4-5-20251001"
    assert s.threshold == pytest.approx(0.75)
    assert s.claude_min == pytest.approx(0.50)
    assert s.api_key is None


def test_env_var_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPERCLAW_MODEL", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("PAPERCLAW_THRESHOLD", "0.9")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    s = load_settings()
    assert s.model == "claude-haiku-4-5-20251001"
    assert s.threshold == pytest.approx(0.9)
    assert s.api_key == "sk-test"


def test_cli_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPERCLAW_MODEL", "env-model")
    s = load_settings(model="cli-model")
    assert s.model == "cli-model"


def test_toml_file_loaded(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "toml-model"\nthreshold = 0.6\n', encoding="utf-8")
    s = load_settings(config_path=cfg)
    assert s.model == "toml-model"
    assert s.threshold == pytest.approx(0.6)


def test_missing_toml_not_an_error(tmp_path: Path) -> None:
    s = load_settings(config_path=tmp_path / "nonexistent.toml")
    assert s.model == "claude-haiku-4-5-20251001"


def test_env_overrides_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "toml-model"\n', encoding="utf-8")
    monkeypatch.setenv("PAPERCLAW_MODEL", "env-model")
    s = load_settings(config_path=cfg)
    assert s.model == "env-model"


def test_cli_overrides_toml(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "toml-model"\n', encoding="utf-8")
    s = load_settings(config_path=cfg, model="cli-model")
    assert s.model == "cli-model"


def test_priority_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "toml-model"\nthreshold = 0.6\n', encoding="utf-8")
    monkeypatch.setenv("PAPERCLAW_THRESHOLD", "0.8")
    s = load_settings(config_path=cfg, model="cli-model")
    assert s.model == "cli-model"
    assert s.threshold == pytest.approx(0.8)


def test_settings_is_frozen() -> None:
    s = Settings()
    with pytest.raises(Exception):
        s.model = "new"  # type: ignore[misc]


def test_inbox_and_library_are_paths() -> None:
    s = Settings()
    assert isinstance(s.inbox, Path)
    assert isinstance(s.library, Path)
