"""Main voice agent - the loop that ties everything together."""

import logging
import re
import signal
import sys
import time
from pathlib import Path

from atlas.core.config import load_config
from atlas.core.brain import Brain
from atlas.core.ears import Ears
from atlas.core.voice import Voice

logger = logging.getLogger("atlas")


class VoiceAgent:
    """The main AI voice agent that listens, thinks, and speaks."""

    def __init__(self, config_path: str | None = None):
        self.config = load_config(config_path)
        self._setup_logging()
        self.brain = Brain(self.config)
        self.ears = Ears(self.config)
        self.voice = Voice(self.config)
        self.running = False

        # Wake word / name detection
        ww_cfg = self.config.get("wake_word", {})
        self.wake_word_enabled = ww_cfg.get("enabled", False)
        self.wake_word = ww_cfg.get("word", "atlas").lower()

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
        logger.info("  Atlas - Local AI Voice Agent - Starting Up")
        logger.info("=" * 50)

        # Load the LLM brain
        logger.info("Loading AI model (first run will download it)...")
        self.brain.initialize()

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
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, shutdown)

        # Greet the user
        greeting = "Hello! I'm Atlas, your local AI assistant. Say my name when you want to talk to me."
        logger.info(greeting)
        self.voice.speak(greeting)

        while self.running:
            try:
                # Listen for speech
                text = self.ears.listen()

                if text is None:
                    continue

                lower = text.lower().strip()

                # Wake word filtering — only respond when the user says "Atlas"
                if self.wake_word_enabled and self.wake_word not in lower:
                    logger.debug("Ignored (no wake word): %s", text)
                    continue

                # Strip the wake word from the input so the LLM gets clean text
                if self.wake_word_enabled:
                    clean = re.sub(
                        rf"\b{re.escape(self.wake_word)}\b[,]?\s*",
                        "",
                        text,
                        flags=re.IGNORECASE,
                    ).strip()
                    if clean:
                        text = clean
                    else:
                        self.voice.speak("Yes? I'm listening.")
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
                time.sleep(1)

        logger.info("Agent stopped.")


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Atlas - Local AI Voice Agent")
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
    parser.add_argument(
        "--train",
        action="store_true",
        help="Fine-tune Atlas's brain with your training data",
    )
    args = parser.parse_args()

    if args.train:
        from atlas.training.train import run_training
        run_training(args.config)
    elif args.text_mode:
        _run_text_mode(args.config)
    else:
        agent = VoiceAgent(args.config)
        agent.initialize()
        agent.run()


def _run_text_mode(config_path: str | None):
    """Run in text-only mode for testing without a microphone."""
    config = load_config(config_path)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    brain = Brain(config)

    print("\n" + "=" * 50)
    print("  Atlas - Local AI Agent (Text Mode)")
    print("  Loading model (first run will download it)...")
    print("=" * 50 + "\n")

    brain.initialize()
    print("Atlas is ready!\n")

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
            print(f"Atlas: {response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
