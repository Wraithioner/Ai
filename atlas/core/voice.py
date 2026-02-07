"""Text-to-Speech module - speaks responses out loud using Piper TTS."""

import logging
import subprocess
from pathlib import Path

from atlas.core.config import VOICE_CACHE_DIR

logger = logging.getLogger(__name__)

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
        try:
            subprocess.run(
                ["piper", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            logger.info("Piper TTS found.")
        except FileNotFoundError:
            logger.error(
                "Piper TTS not found. Install it with: pip install piper-tts"
            )
            raise RuntimeError("Piper TTS is not installed.")

        VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.model_path = VOICE_CACHE_DIR / f"{self.voice_name}.onnx"
        self.config_path = VOICE_CACHE_DIR / f"{self.voice_name}.onnx.json"

        if not self.model_path.exists():
            self._download_voice()

    def _download_voice(self):
        """Download the voice model from HuggingFace."""
        import requests

        model_url = VOICE_URLS.get(self.voice_name)
        if not model_url:
            parts = self.voice_name.split("-")
            lang = parts[0]
            lang_short = lang.split("_")[0]
            name = parts[1]
            quality = parts[2]
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
            piper_cmd = [
                "piper",
                "--model", str(self.model_path),
                "--output-raw",
            ]
            if self.rate != 1.0:
                piper_cmd.extend(["--length-scale", str(1.0 / self.rate)])

            piper_proc = subprocess.Popen(
                piper_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            raw_audio, _ = piper_proc.communicate(
                input=text.encode("utf-8"), timeout=60
            )

            if not raw_audio:
                logger.warning("Piper produced no audio output.")
                return

            self._play_raw_audio(raw_audio)
            logger.debug("Finished speaking.")

        except subprocess.TimeoutExpired:
            logger.warning("Speech generation timed out.")
            piper_proc.kill()
        except Exception as e:
            logger.error("TTS error: %s", e)

    def _play_raw_audio(self, raw_audio: bytes):
        """Play raw PCM audio data using PyAudio (works on Windows, Mac, Linux)."""
        import pyaudio

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pa.get_format_from_width(2),
            channels=1,
            rate=22050,
            output=True,
            output_device_index=self.output_device,
        )

        try:
            chunk_size = 4096
            for i in range(0, len(raw_audio), chunk_size):
                stream.write(raw_audio[i:i + chunk_size])
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
