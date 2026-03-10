"""Configuration loader using YAML and environment variables."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to the config.yaml file. Defaults to config/config.yaml
                     relative to the project root.

    Returns:
        Dictionary with all configuration values.
    """
    load_dotenv()

    if config_path is None:
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "config.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config.setdefault("api_keys", {})
    config["api_keys"]["openrouter"] = os.getenv("OPENROUTER_API_KEY", "")

    return config
