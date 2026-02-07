"""Text-to-Speech module - speaks responses out loud.

Uses Piper TTS (Linux) or pyttsx3/Windows SAPI (Windows) as a fallback.
"""

import logging
import subprocess
import sys
from pathlib import Path

from atlas.core.config import VOICE_CACHE_DIR

logger = logging.getLogger(__name__)

# Map of friendly voice names to download URLs (for Piper)
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
    """Converts text to speech and plays it through the speakers."""

    def __init__(self, config: dict):
        tts_cfg = config["tts"]
        audio_cfg = config["audio"]
        self.voice_name = tts_cfg.get("voice", "en_US-amy-medium")
        self.rate = tts_cfg.get("rate", 1.0)
        self.output_device = audio_cfg.get("output_device")
        self.model_path = None
        self.config_path = None
        self._use_piper = False
        self._use_sapi = False

    def initialize(self):
        """Set up TTS engine. Tries Piper first, falls back to pyttsx3."""
        # Try Piper TTS first
        if self._try_piper():
            self._use_piper = True
            logger.info("Using Piper TTS engine.")
            return

        # Fall back to Windows SAPI directly
        if self._try_sapi():
            self._use_sapi = True
            logger.info("Using Windows SAPI TTS engine.")
            return

        raise RuntimeError(
            "No TTS engine available. Install pywin32: pip install pywin32"
        )

    def _try_piper(self) -> bool:
        """Check if Piper TTS is available."""
        try:
            subprocess.run(
                ["piper", "--version"],
                capture_output=True, text=True, timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.debug("Piper TTS not found, will try fallback.")
            return False

        VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.model_path = VOICE_CACHE_DIR / f"{self.voice_name}.onnx"
        self.config_path = VOICE_CACHE_DIR / f"{self.voice_name}.onnx.json"

        if not self.model_path.exists():
            self._download_voice()

        return True

    def _try_sapi(self) -> bool:
        """Check if Windows SAPI is available (via win32com)."""
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            # Quick test — just check we can access Rate
            _ = speaker.Rate
            return True
        except Exception:
            pass

        # Fallback: try comtypes directly (already installed via pyttsx3)
        try:
            import comtypes.client
            speaker = comtypes.client.CreateObject("SAPI.SpVoice")
            _ = speaker.Rate
            return True
        except Exception as e:
            logger.debug("Windows SAPI not available: %s", e)
            return False

    def _download_voice(self):
        """Download the Piper voice model from HuggingFace."""
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

        if self._use_piper:
            self._speak_piper(text)
        elif self._use_sapi:
            self._speak_sapi(text)

    def _speak_piper(self, text: str):
        """Speak using Piper TTS."""
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
            logger.error("Piper TTS error: %s", e)

    def _speak_sapi(self, text: str):
        """Speak using Windows SAPI directly (no pyttsx3 wrapper)."""
        try:
            logger.info("Speaking out loud: %s", text[:80])
            try:
                import win32com.client
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
            except Exception:
                import comtypes.client
                speaker = comtypes.client.CreateObject("SAPI.SpVoice")

            # Rate: -10 (slow) to 10 (fast), 0 is default
            speaker.Rate = int((self.rate - 1.0) * 5)
            speaker.Volume = 100
            # Speak synchronously (blocks until done)
            speaker.Speak(text)
            logger.info("Finished speaking.")
        except Exception as e:
            logger.error("SAPI TTS error: %s", e, exc_info=True)

    def _play_raw_audio(self, raw_audio: bytes):
        """Play raw PCM audio data using PyAudio (for Piper output)."""
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
