"""Configuration loader for the AI voice agent."""

import os
from pathlib import Path

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)
    # Expand ~ in log path
    log_file = config.get("logging", {}).get("file", "")
    if log_file:
        config["logging"]["file"] = os.path.expanduser(log_file)
    return config
