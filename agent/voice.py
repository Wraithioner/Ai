"""Text-to-Speech module - speaks responses out loud using Piper TTS."""

import io
import logging
import subprocess
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

PIPER_VOICES_DIR = Path.home() / ".local" / "share" / "piper-voices"

# Map of friendly voice names to download URLs
VOICE_URLS = {
    "en_US-amy-medium": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
        "en/en_US/amy/medium/en_US-amy-medium.onnx"
    ),
    "en_US-lessac-medium": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
        "en/en_US/lessac/medium/en_US-lessac-medium.onnx"
    ),
    "en_GB-alan-medium": (
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
        "en/en_GB/alan/medium/en_GB-alan-medium.onnx"
    ),
}


class Voice:
    """Converts text to speech using Piper TTS (fully offline)."""

    def __init__(self, config: dict):
        tts_cfg = config["tts"]
        audio_cfg = config["audio"]
        self.voice_name = tts_cfg.get("voice", "en_US-amy-medium")
        self.rate = tts_cfg.get("rate", 1.0)
        self.output_device = audio_cfg.get("output_device")
        self.model_path = None
        self.config_path = None

    def initialize(self):
        """Ensure Piper is installed and voice model is available."""
        # Check if piper is installed
        try:
            result = subprocess.run(
                ["piper", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            logger.info("Piper TTS found.")
        except FileNotFoundError:
            logger.error(
                "Piper TTS not found. Install it with: "
                "pip install piper-tts"
            )
            raise RuntimeError("Piper TTS is not installed.")

        # Set up voice model path
        PIPER_VOICES_DIR.mkdir(parents=True, exist_ok=True)
        self.model_path = PIPER_VOICES_DIR / f"{self.voice_name}.onnx"
        self.config_path = PIPER_VOICES_DIR / f"{self.voice_name}.onnx.json"

        if not self.model_path.exists():
            self._download_voice()

    def _download_voice(self):
        """Download the voice model from HuggingFace."""
        import requests

        model_url = VOICE_URLS.get(self.voice_name)
        if not model_url:
            # Construct URL from voice name pattern
            parts = self.voice_name.split("-")
            lang = parts[0]  # e.g., en_US
            lang_short = lang.split("_")[0]  # e.g., en
            name = parts[1]  # e.g., amy
            quality = parts[2]  # e.g., medium
            model_url = (
                f"https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                f"{lang_short}/{lang}/{name}/{quality}/{self.voice_name}.onnx"
            )

        config_url = model_url + ".json"

        logger.info("Downloading voice model '%s'...", self.voice_name)
        for url, path in [
            (model_url, self.model_path),
            (config_url, self.config_path),
        ]:
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        logger.info("Voice model downloaded to %s", self.model_path)

    def speak(self, text: str):
        """Convert text to speech and play it through the speakers."""
        if not text:
            return

        logger.debug("Speaking: %s", text[:80])

        try:
            # Use piper to generate WAV audio, pipe to aplay
            piper_cmd = [
                "piper",
                "--model", str(self.model_path),
                "--output-raw",
            ]
            if self.rate != 1.0:
                piper_cmd.extend(["--length-scale", str(1.0 / self.rate)])

            aplay_cmd = [
                "aplay",
                "-r", "22050",
                "-f", "S16_LE",
                "-t", "raw",
                "-c", "1",
                "-q",  # quiet
            ]

            # Pipe piper output directly to aplay
            piper_proc = subprocess.Popen(
                piper_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            aplay_proc = subprocess.Popen(
                aplay_cmd,
                stdin=piper_proc.stdout,
                stderr=subprocess.PIPE,
            )

            # Send text to piper
            piper_proc.stdin.write(text.encode("utf-8"))
            piper_proc.stdin.close()

            # Wait for playback to finish
            aplay_proc.wait(timeout=60)
            piper_proc.wait(timeout=10)

            logger.debug("Finished speaking.")

        except FileNotFoundError as e:
            if "aplay" in str(e):
                logger.error(
                    "aplay not found. Install alsa-utils: "
                    "sudo apt install alsa-utils"
                )
            else:
                raise
        except subprocess.TimeoutExpired:
            logger.warning("Speech playback timed out.")
        except Exception as e:
            logger.error("TTS error: %s", e)
