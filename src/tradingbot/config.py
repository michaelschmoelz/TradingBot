"""Konfiguration laden: config/config.yaml + .env (Keys).

Parameter kommen aus der Config, nie als Konstanten in den Code (Projektregel).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """YAML-Config laden und .env in die Umgebung übernehmen."""
    load_dotenv(REPO_ROOT / ".env")
    with open(path or CONFIG_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def require_env(*names: str) -> dict[str, str]:
    """Benötigte Env-Variablen einsammeln; fehlende gesammelt melden."""
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError(
            "Fehlende Umgebungsvariablen: " + ", ".join(missing)
            + " — lokal in .env eintragen (siehe .env.example), in CI als GitHub Secrets."
        )
    return {n: os.environ[n] for n in names}
