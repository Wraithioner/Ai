"""Entry point — starts the Telegram bot with LLM brain and Arena integration."""

import logging
import sys

from atlas.core.config import load_config
from atlas.core.brain import Brain
from atlas.arena.client import ArenaClient
from atlas.telegram.bot import TelegramBot


def main():
    """Load config, initialize LLM + Arena, and start the Telegram bot."""
    config = load_config()

    # Logging — Railway captures stdout, no file needed
    log_level = config.get("logging", {}).get("level", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger("atlas")

    logger.info("=" * 40)
    logger.info("  Agent Telegram Bot — Starting")
    logger.info("=" * 40)

    # Validate required config
    tg_cfg = config.get("telegram", {})
    if not tg_cfg.get("bot_token"):
        logger.error("TELEGRAM_BOT_TOKEN not set. Cannot start.")
        sys.exit(1)

    owner_id = tg_cfg.get("owner_id", 0)
    if not owner_id:
        logger.warning("OWNER_ID not set — bot will reject all messages (owner-only mode).")
    else:
        logger.info("Owner ID: %d", owner_id)

    # Validate model config
    if not config.get("llm", {}).get("model"):
        logger.error("No model specified. Set MODEL_NAME env var or llm.model in settings.yaml.")
        sys.exit(1)

    # Load the LLM
    logger.info("Loading AI model (first run downloads it)...")
    brain = Brain(config)
    try:
        brain.initialize()
    except Exception as e:
        logger.error("Failed to load AI model: %s", e)
        logger.error("Check MODEL_NAME, available RAM, and network access on Railway.")
        sys.exit(1)
    logger.info("Model ready on %s.", brain.device)

    # Initialize Arena client
    arena = ArenaClient(config)
    if arena.configured:
        logger.info("Arena configured (handle: %s, agent: %s)", arena.handle, arena.agent_id)
    else:
        logger.warning("Arena credentials not set — Arena features disabled.")

    # Start the Telegram bot (blocking — handles SIGTERM from Railway)
    bot = TelegramBot(brain, config, arena=arena)
    bot.run()


if __name__ == "__main__":
    main()
