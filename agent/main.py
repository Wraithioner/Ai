"""Main voice agent - the loop that ties everything together."""

import logging
import signal
import sys
import time
from pathlib import Path

from agent.config import load_config
from agent.brain import Brain
from agent.ears import Ears
from agent.voice import Voice

logger = logging.getLogger("agent")


class VoiceAgent:
    """The main AI voice agent that listens, thinks, and speaks."""

    def __init__(self, config_path: str | None = None):
        self.config = load_config(config_path)
        self._setup_logging()
        self.brain = Brain(self.config)
        self.ears = Ears(self.config)
        self.voice = Voice(self.config)
        self.running = False

    def _setup_logging(self):
        log_cfg = self.config.get("logging", {})
        level = getattr(logging, log_cfg.get("level", "INFO"))
        log_file = log_cfg.get("file")

        handlers = [logging.StreamHandler(sys.stdout)]
        if log_file:
            log_dir = Path(log_file).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file))

        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=handlers,
        )

    def initialize(self):
        """Initialize all components."""
        logger.info("=" * 50)
        logger.info("  Local AI Voice Agent - Starting Up")
        logger.info("=" * 50)

        # Check Ollama connection
        logger.info("Checking Ollama connection...")
        if not self.brain.check_connection():
            logger.error(
                "Cannot connect to Ollama or model not found.\n"
                "1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh\n"
                "2. Start Ollama: ollama serve\n"
                "3. Pull a model: ollama pull %s",
                self.brain.model,
            )
            sys.exit(1)

        # Load speech-to-text
        logger.info("Initializing speech recognition...")
        self.ears.initialize()

        # Load text-to-speech
        logger.info("Initializing voice synthesis...")
        self.voice.initialize()

        logger.info("All systems ready!")

    def run(self):
        """Main loop: listen -> think -> speak -> repeat."""
        self.running = True

        # Handle graceful shutdown
        def shutdown(signum, frame):
            logger.info("Shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        # Greet the user
        greeting = "Hello! I'm your local AI assistant. I'm listening."
        logger.info(greeting)
        self.voice.speak(greeting)

        while self.running:
            try:
                # Listen for speech
                text = self.ears.listen()

                if text is None:
                    continue

                # Handle special commands
                lower = text.lower().strip()
                if lower in ("goodbye", "shut down", "turn off", "exit", "quit"):
                    farewell = "Goodbye! Shutting down."
                    logger.info(farewell)
                    self.voice.speak(farewell)
                    self.running = False
                    break

                if lower in ("reset", "clear memory", "forget everything"):
                    self.brain.reset_conversation()
                    msg = "Memory cleared. Starting fresh."
                    self.voice.speak(msg)
                    continue

                # Think (send to LLM)
                logger.info("Thinking...")
                response = self.brain.think(text)
                logger.info("Response: %s", response[:100])

                # Speak the response
                self.voice.speak(response)

            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                logger.error("Error in main loop: %s", e, exc_info=True)
                time.sleep(1)  # Prevent tight error loops

        logger.info("Agent stopped.")


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Local AI Voice Agent")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default=None,
    )
    parser.add_argument(
        "--text-mode",
        action="store_true",
        help="Run in text mode (type instead of speak)",
    )
    args = parser.parse_args()

    if args.text_mode:
        _run_text_mode(args.config)
    else:
        agent = VoiceAgent(args.config)
        agent.initialize()
        agent.run()


def _run_text_mode(config_path: str | None):
    """Run in text-only mode for testing without a microphone."""
    config = load_config(config_path)

    # Set up basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    brain = Brain(config)
    if not brain.check_connection():
        logger.error("Cannot connect to Ollama. Make sure it's running.")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("  Local AI Agent - Text Mode")
    print("  Type 'quit' to exit, 'reset' to clear memory")
    print("=" * 50 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit"):
                print("Goodbye!")
                break
            if user_input.lower() in ("reset", "clear"):
                brain.reset_conversation()
                print("Memory cleared.\n")
                continue

            response = brain.think(user_input)
            print(f"AI: {response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
