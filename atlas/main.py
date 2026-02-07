"""Main voice agent - the loop that ties everything together."""

import logging
import re
import signal
import sys
import time
from pathlib import Path

from atlas.core.config import load_config
from atlas.core.actions import Actions
from atlas.core.brain import Brain
from atlas.core.computer import Computer
from atlas.core.ears import Ears
from atlas.core.eyes import Eyes
from atlas.core.safety import Safety
from atlas.core.voice import Voice

logger = logging.getLogger("atlas")


class VoiceAgent:
    """The main AI voice agent that listens, thinks, speaks, and controls the computer."""

    def __init__(self, config_path: str | None = None):
        self.config = load_config(config_path)
        self._setup_logging()
        self.actions = Actions()
        self.brain = Brain(self.config)
        self.computer = Computer(self.config)
        self.ears = Ears(self.config)
        self.eyes = Eyes(self.config)
        self.safety = Safety(self.config)
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

    def _agent_loop(self, task: str):
        """Run the observe-plan-execute loop for computer control tasks."""
        max_steps = self.safety.max_steps
        logger.info("Agent loop started for task: %s (max %d steps)", task, max_steps)

        for step in range(max_steps):
            logger.info("Agent step %d/%d", step + 1, max_steps)

            try:
                # 1. Observe — read the screen
                screen_text = self.eyes.read_screen()
                if not screen_text:
                    self.voice.speak("I can't read the screen right now.")
                    break

                # 2. Plan — ask the Brain what to do next
                action = self.brain.plan_action(task, screen_text)
                logger.info("Planned action: %s", action)

                action_type = action.get("action", "fail")
                reason = action.get("reason", "")

                # 3. Check if task is done or failed
                if action_type == "done":
                    msg = f"Done. {reason}" if reason else "Done."
                    logger.info("Agent completed: %s", msg)
                    self.voice.speak(msg)
                    break

                if action_type == "fail":
                    msg = f"I couldn't do that. {reason}" if reason else "I couldn't figure out how to do that."
                    logger.warning("Agent failed: %s", msg)
                    self.voice.speak(msg)
                    break

                # 4. Safety check
                safe, safety_reason = self.safety.check_action(action, screen_text)
                if not safe:
                    self.voice.speak(safety_reason)
                    logger.warning("Safety blocked action: %s", safety_reason)
                    break

                # 5. Execute the action
                if action_type == "click":
                    target = action.get("target", "")
                    coords = self.eyes.find_text(target)
                    if coords:
                        self.computer.click(*coords)
                    else:
                        self.voice.speak(f"I can't find '{target}' on the screen.")
                        break

                elif action_type == "type":
                    value = action.get("value", "")
                    self.computer.type_text(value)

                elif action_type == "press":
                    key = action.get("value", "enter")
                    self.computer.press_key(key)

                elif action_type == "hotkey":
                    keys_str = action.get("value", "")
                    keys = [k.strip() for k in keys_str.split("+")]
                    self.computer.hotkey(*keys)

                elif action_type == "scroll":
                    direction = action.get("value", "down")
                    clicks = 3 if direction == "down" else -3
                    self.computer.scroll(clicks)

                else:
                    logger.warning("Unknown action type: %s", action_type)
                    break

                # Wait for the screen to update before next step
                time.sleep(1.5)

            except Exception as e:
                logger.error("Agent loop error at step %d: %s", step + 1, e, exc_info=True)
                self.voice.speak("Something went wrong while controlling the computer.")
                break
        else:
            self.voice.speak(f"Reached the maximum of {max_steps} steps. Stopping.")
            logger.info("Agent loop hit max steps (%d).", max_steps)

        # Unload eyes if configured
        if self.eyes.unload_after_use:
            self.eyes.unload()

    def _speak_interruptible(self, text: str):
        """Speak text asynchronously while polling the always-on mic.

        Starts SAPI async speech, then polls each audio chunk in
        real-time on the persistent mic stream. If the user speaks
        loud enough to pass the high VAD threshold (0.85), it records
        the utterance, transcribes it, and either stops or processes it.
        """
        if not text:
            return

        # Start speaking without blocking
        self.voice.speak_async(text)

        # Poll the always-on mic continuously while Atlas speaks
        while self.voice.is_speaking():
            heard = self.ears.poll_for_speech(vad_threshold=0.85)

            if heard:
                if self._is_stop_command(heard):
                    self.voice.stop()
                    logger.info("User interrupted with stop: %s", heard)
                    self.voice.speak("Okay.")
                    return
                else:
                    self.voice.stop()
                    logger.info("User interrupted with new input: %s", heard)
                    self._handle_input(heard)
                    return

    def _handle_input(self, text: str):
        """Process a single user input (used by main loop and interrupt handler)."""
        lower = text.lower().strip()

        # Try action handler first
        handled, action_response = self.actions.try_handle(text)
        if handled:
            if action_response == "__EYES__":
                self.voice.speak("Let me look at your screen.")
                try:
                    description = self.eyes.look()
                    logger.info("Screen: %s", description[:100])
                    self._speak_interruptible(description)
                except Exception as e:
                    logger.error("Vision error: %s", e)
                    self.voice.speak("Sorry, I had trouble seeing the screen.")
            elif action_response == "__COMPUTER__":
                if not self.computer.enabled:
                    self.voice.speak(
                        "Computer control is disabled. "
                        "Enable it in settings dot yaml."
                    )
                else:
                    self.voice.speak("On it.")
                    self._agent_loop(text)
            elif action_response:
                logger.info("Action: %s", action_response)
                self.voice.speak(action_response)
            return

        if lower in ("goodbye", "shut down", "turn off", "exit", "quit"):
            farewell = "Goodbye! Shutting down."
            logger.info(farewell)
            self.voice.speak(farewell)
            self.running = False
            return

        if lower in ("reset", "clear memory", "forget everything"):
            self.brain.reset_conversation()
            self.voice.speak("Memory cleared. Starting fresh.")
            return

        # Think (send to LLM)
        logger.info("Thinking...")
        response = self.brain.think(text)
        logger.info("Response: %s", response[:100])

        # Speak interruptibly
        self._speak_interruptible(response)

    def _is_stop_command(self, text: str) -> bool:
        """Check if text is a stop/interrupt command."""
        lower = text.lower().strip()
        stop_words = [
            "stop", "cancel", "abort", "halt",
            "nevermind", "never mind", "shut up",
        ]
        if any(sw in lower for sw in stop_words):
            return True
        # Check after stripping wake word
        if self.wake_word_enabled:
            for variant in [
                self.wake_word, "at last", "at less", "adless",
                "atlast", "atlass", "atlus", "at las",
            ]:
                lower = re.sub(
                    rf"\b{re.escape(variant)}\b[,]?\s*",
                    "", lower, flags=re.IGNORECASE,
                ).strip()
            if any(sw in lower for sw in stop_words):
                return True
        return False

    def run(self):
        """Main loop: listen -> think -> speak -> repeat.

        The mic is always on (opened once at startup). While Atlas
        speaks, the mic polls every chunk (~32ms) for interrupts.
        Say "stop" to cancel speech, or say something new.
        """
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
                # Listen for speech (blocks until speech detected)
                text = self.ears.listen()

                if text is None:
                    continue

                lower = text.lower().strip()

                # Check for stop/interrupt FIRST
                if self._is_stop_command(text):
                    self.voice.stop()
                    logger.info("User said stop: %s", text)
                    self.voice.speak("Okay.")
                    continue

                # Wake word filtering
                if self.wake_word_enabled:
                    wake_variants = [
                        self.wake_word, "at last", "at less", "adless",
                        "atlast", "atlass", "atlus", "at las",
                    ]
                    found_wake = False
                    for variant in wake_variants:
                        if variant in lower:
                            found_wake = True
                            break
                    if not found_wake:
                        logger.debug("Ignored (no wake word): %s", text)
                        continue

                # Strip the wake word
                if self.wake_word_enabled:
                    clean = text
                    for variant in [
                        self.wake_word, "at last", "at less", "adless",
                        "atlast", "atlass", "atlus", "at las",
                    ]:
                        clean = re.sub(
                            rf"\b{re.escape(variant)}\b[,]?\s*",
                            "",
                            clean,
                            flags=re.IGNORECASE,
                        ).strip()
                    if clean:
                        text = clean
                    else:
                        self.voice.speak("Yes? I'm listening.")
                        continue

                    # Check if cleaned text is a stop command
                    if self._is_stop_command(clean):
                        self.voice.stop()
                        logger.info("User said stop: %s", text)
                        self.voice.speak("Okay.")
                        continue

                # Handle the input (actions, LLM, etc.)
                self._handle_input(text)

            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                logger.error("Error in main loop: %s", e, exc_info=True)
                time.sleep(1)

        # Close the mic stream
        self.ears.shutdown()
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

    actions = Actions()
    brain = Brain(config)
    computer = Computer(config)
    eyes = Eyes(config)
    safety = Safety(config)

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

            # Try action handler first
            handled, action_response = actions.try_handle(user_input)
            if handled:
                if action_response == "__EYES__":
                    print("Atlas: Let me read the screen...\n")
                    try:
                        description = eyes.look()
                        print(f"Atlas: {description}\n")
                    except Exception as e:
                        print(f"Atlas: Sorry, I had trouble reading the screen. {e}\n")
                elif action_response == "__COMPUTER__":
                    if not computer.enabled:
                        print("Atlas: Computer control is disabled. Enable it in settings.yaml\n")
                    else:
                        print("Atlas: On it.\n")
                        _text_agent_loop(user_input, brain, computer, eyes, safety)
                elif action_response:
                    print(f"Atlas: {action_response}\n")
                continue

            response = brain.think(user_input)
            print(f"Atlas: {response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


def _text_agent_loop(task: str, brain: Brain, computer: Computer, eyes: Eyes, safety: Safety):
    """Agent loop for text mode — same logic as VoiceAgent._agent_loop but prints."""
    max_steps = safety.max_steps

    for step in range(max_steps):
        print(f"  [Step {step + 1}/{max_steps}]")

        try:
            screen_text = eyes.read_screen()
            if not screen_text:
                print("Atlas: I can't read the screen right now.\n")
                break

            action = brain.plan_action(task, screen_text)
            print(f"  Action: {action}")

            action_type = action.get("action", "fail")
            reason = action.get("reason", "")

            if action_type == "done":
                print(f"Atlas: Done. {reason}\n")
                break

            if action_type == "fail":
                print(f"Atlas: Couldn't do that. {reason}\n")
                break

            safe, safety_reason = safety.check_action(action, screen_text)
            if not safe:
                print(f"Atlas: {safety_reason}\n")
                break

            if action_type == "click":
                target = action.get("target", "")
                coords = eyes.find_text(target)
                if coords:
                    computer.click(*coords)
                else:
                    print(f"Atlas: Can't find '{target}' on screen.\n")
                    break
            elif action_type == "type":
                computer.type_text(action.get("value", ""))
            elif action_type == "press":
                computer.press_key(action.get("value", "enter"))
            elif action_type == "hotkey":
                keys = [k.strip() for k in action.get("value", "").split("+")]
                computer.hotkey(*keys)
            elif action_type == "scroll":
                direction = action.get("value", "down")
                computer.scroll(3 if direction == "down" else -3)
            else:
                print(f"Atlas: Unknown action type: {action_type}\n")
                break

            import time
            time.sleep(1.5)

        except Exception as e:
            print(f"Atlas: Error during computer control: {e}\n")
            break
    else:
        print(f"Atlas: Reached max {max_steps} steps. Stopping.\n")

    if eyes.unload_after_use:
        eyes.unload()


if __name__ == "__main__":
    main()
