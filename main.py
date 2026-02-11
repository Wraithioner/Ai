"""Entry point — start the agent."""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

from agent.bot import run_bot

if __name__ == "__main__":
    run_bot()
