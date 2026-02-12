"""Configuration loader with environment variable overrides for Railway."""

import os
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
LOG_DIR = PROJECT_ROOT / "logs"

# Local project directories
MODELS_DIR = PROJECT_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"
TRAINING_DATA_DIR = DATA_DIR / "training"


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from YAML file with environment variable overrides.

    Environment variables take precedence over YAML values. This is how
    Railway injects configuration (Settings > Variables).

    Supported env vars:
        TELEGRAM_BOT_TOKEN       - Telegram bot token (required)
        OWNER_ID                 - Telegram user ID of the bot owner/admin
        MODEL_NAME               - HuggingFace model ID
        SYSTEM_PROMPT            - LLM system prompt
        MAX_TOKENS               - Max response tokens
        TEMPERATURE              - LLM temperature (0.0-1.0)
        CONTEXT_WINDOW           - Conversation history length
        MAX_USERS                - Max concurrent users in memory
        LOG_LEVEL                - Logging level
        ARENA_API_KEY            - Arena platform API key
        ARENA_AGENT_ID           - Arena agent ID
        ARENA_HANDLE             - Arena handle/username
        ARENA_VERIFICATION_CODE  - Arena verification code
        ARENA_WALLET             - Arena wallet address
        ARENA_WALLET_PRIVATE_KEY - Arena wallet private key
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        with open(path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    # Ensure required sections exist
    config.setdefault("telegram", {})
    config.setdefault("llm", {})
    config.setdefault("arena", {})
    config.setdefault("safety", {})
    config.setdefault("logging", {})

    # --- Telegram ---
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        config["telegram"]["bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]

    if os.environ.get("OWNER_ID"):
        config["telegram"]["owner_id"] = int(os.environ["OWNER_ID"])

    if os.environ.get("MAX_USERS"):
        config["telegram"]["max_users"] = int(os.environ["MAX_USERS"])

    # --- LLM ---
    if os.environ.get("MODEL_NAME"):
        config["llm"]["model"] = os.environ["MODEL_NAME"]

    if os.environ.get("SYSTEM_PROMPT"):
        config["llm"]["system_prompt"] = os.environ["SYSTEM_PROMPT"]

    if os.environ.get("MAX_TOKENS"):
        config["llm"]["max_tokens"] = int(os.environ["MAX_TOKENS"])

    if os.environ.get("TEMPERATURE"):
        config["llm"]["temperature"] = float(os.environ["TEMPERATURE"])

    if os.environ.get("CONTEXT_WINDOW"):
        config["llm"]["context_window"] = int(os.environ["CONTEXT_WINDOW"])

    # --- Arena ---
    if os.environ.get("ARENA_API_KEY"):
        config["arena"]["api_key"] = os.environ["ARENA_API_KEY"]

    if os.environ.get("ARENA_AGENT_ID"):
        config["arena"]["agent_id"] = os.environ["ARENA_AGENT_ID"]

    if os.environ.get("ARENA_HANDLE"):
        config["arena"]["handle"] = os.environ["ARENA_HANDLE"]

    if os.environ.get("ARENA_VERIFICATION_CODE"):
        config["arena"]["verification_code"] = os.environ["ARENA_VERIFICATION_CODE"]

    if os.environ.get("ARENA_WALLET"):
        config["arena"]["wallet"] = os.environ["ARENA_WALLET"]

    if os.environ.get("ARENA_WALLET_PRIVATE_KEY"):
        config["arena"]["wallet_private_key"] = os.environ["ARENA_WALLET_PRIVATE_KEY"]

    # --- Logging ---
    if os.environ.get("LOG_LEVEL"):
        config["logging"]["level"] = os.environ["LOG_LEVEL"]

    return config
