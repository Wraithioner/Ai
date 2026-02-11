"""Configuration — reads from Railway environment variables."""

import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "none")  # none | openai | anthropic
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))  # your Telegram user ID for auth
