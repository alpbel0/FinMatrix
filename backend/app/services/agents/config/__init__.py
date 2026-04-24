"""Helpers for loading agent YAML configuration files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


CONFIG_DIR = Path(__file__).resolve().parent
AGENTS_CONFIG_PATH = CONFIG_DIR / "agents.yaml"
TASKS_CONFIG_PATH = CONFIG_DIR / "tasks.yaml"


def _load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ValueError(f"YAML config must contain a top-level mapping: {path}")

    return data


@lru_cache(maxsize=1)
def load_agents_config() -> dict[str, Any]:
    return _load_yaml_file(AGENTS_CONFIG_PATH)


@lru_cache(maxsize=1)
def load_tasks_config() -> dict[str, Any]:
    return _load_yaml_file(TASKS_CONFIG_PATH)


__all__ = [
    "AGENTS_CONFIG_PATH",
    "TASKS_CONFIG_PATH",
    "load_agents_config",
    "load_tasks_config",
]

