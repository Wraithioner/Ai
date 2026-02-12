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
    logger.info("  AI Telegram Bot — Starting")
    logger.info("=" * 40)

    # Load the LLM
    logger.info("Loading AI model (first run downloads it)...")
    brain = Brain(config)
    brain.initialize()
    logger.info("Model ready.")

    # Initialize Arena client
    arena = ArenaClient(config)
    if arena.configured:
        logger.info("Arena client configured (handle: %s)", arena.handle)
    else:
        logger.warning("Arena credentials not set — Arena features disabled.")

    # Start the Telegram bot
    bot = TelegramBot(brain, config, arena=arena)
    bot.run()


if __name__ == "__main__":
    main()
