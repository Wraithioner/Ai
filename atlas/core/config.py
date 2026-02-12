"""Configuration loader for Atlas."""

import sys
from pathlib import Path

import yaml

# Project root is two levels up from this file (atlas/core/config.py -> Ai/)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"

# Cross-platform directories
if sys.platform == "win32":
    CACHE_DIR = Path.home() / "AppData" / "Local" / "atlas"
else:
    CACHE_DIR = Path.home() / ".local" / "share" / "atlas"

# Organized subdirectories
MODEL_CACHE_DIR = CACHE_DIR / "models"
VOICE_CACHE_DIR = CACHE_DIR / "voices"
LOG_DIR = PROJECT_ROOT / "logs"

# Local project directories
MODELS_DIR = PROJECT_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"
TRAINING_DATA_DIR = DATA_DIR / "training"


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)

    # Resolve relative log file paths to project logs/ directory
    log_file = config.get("logging", {}).get("file", "")
    if log_file and not Path(log_file).is_absolute():
        config["logging"]["file"] = str(LOG_DIR / Path(log_file).name)

    return config
