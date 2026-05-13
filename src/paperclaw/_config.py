from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Settings(BaseModel):
    model_config = {"frozen": True}

    api_key: str | None = None
    model: str = "claude-haiku-4-5-20251001"
    threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    claude_min: float = Field(default=0.50, ge=0.0, le=1.0)
    inbox: Path = Field(default_factory=lambda: Path.home() / "inbox")
    library: Path = Field(default_factory=lambda: Path.home() / "library")


_ENV_MAP: dict[str, str] = {
    "ANTHROPIC_API_KEY": "api_key",
    "PAPERCLAW_MODEL": "model",
    "PAPERCLAW_THRESHOLD": "threshold",
    "PAPERCLAW_CLAUDE_MIN": "claude_min",
    "PAPERCLAW_INBOX": "inbox",
    "PAPERCLAW_LIBRARY": "library",
}


def _resolve_config_file(config_path: Path | None) -> Path | None:
    if config_path is not None:
        return config_path
    env = os.environ.get("PAPERCLAW_CONFIG")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "paperclaw" / "config.toml"


def load_settings(
    config_path: Path | None = None,
    **cli_overrides: Any,
) -> Settings:
    merged: dict[str, Any] = {}

    cfg_file = _resolve_config_file(config_path)
    if cfg_file and cfg_file.exists():
        with open(cfg_file, "rb") as fh:
            merged.update(tomllib.load(fh))

    for env_var, key in _ENV_MAP.items():
        val = os.environ.get(env_var)
        if val is not None:
            merged[key] = val

    for key, val in cli_overrides.items():
        if val is not None:
            merged[key] = val

    return Settings(**merged)
