"""Text-to-Speech module - speaks responses out loud.

Uses Piper TTS (Linux) or Windows SAPI (Windows) as a fallback.
Both engines support async speech with interrupt capability.
"""

import logging
import subprocess
import sys
import threading
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
    """Converts text to speech and plays it through the speakers.

    Both Piper and SAPI support async speech with interrupt capability.
    Piper async runs synthesis + playback in a background thread.
    Uses a persistent PyAudio output stream to avoid open/close overhead per speech.
    """

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
        self._speaking = False
        self._stop_requested = False
        self._sapi_speaker = None
        self._speech_thread = None
        self._lock = threading.Lock()
        # Persistent PyAudio output (initialized on first Piper speak)
        self._pa = None
        self._out_stream = None
        self._piper_sample_rate = 22050  # Updated from voice config JSON

    def initialize(self):
        """Set up TTS engine. Tries Piper first, falls back to Windows SAPI."""
        if self._try_piper():
            self._use_piper = True
            logger.info("Using Piper TTS engine.")
            return

        if self._try_sapi():
            self._use_sapi = True
            logger.info("Using Windows SAPI TTS engine.")
            return

        raise RuntimeError(
            "No TTS engine available. Install piper-tts or pywin32."
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

        # Read sample rate from the Piper voice config JSON
        self._piper_sample_rate = self._read_piper_sample_rate()

        return True

    def _try_sapi(self) -> bool:
        """Check if Windows SAPI is available and create a persistent speaker."""
        try:
            import win32com.client
            self._sapi_speaker = win32com.client.Dispatch("SAPI.SpVoice")
            _ = self._sapi_speaker.Rate
            return True
        except Exception:
            pass

        try:
            import comtypes.client
            self._sapi_speaker = comtypes.client.CreateObject("SAPI.SpVoice")
            _ = self._sapi_speaker.Rate
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

    def _read_piper_sample_rate(self) -> int:
        """Read the sample rate from the Piper voice config JSON."""
        import json
        try:
            if self.config_path and self.config_path.exists():
                with open(self.config_path) as f:
                    voice_cfg = json.load(f)
                rate = voice_cfg.get("audio", {}).get("sample_rate", 22050)
                logger.info("Piper voice sample rate: %d Hz", rate)
                return rate
        except Exception as e:
            logger.debug("Could not read Piper config, using 22050 Hz: %s", e)
        return 22050

    def _get_output_stream(self):
        """Get or create a persistent PyAudio output stream for Piper playback."""
        import pyaudio

        if self._out_stream is not None:
            try:
                if self._out_stream.is_active() or not self._out_stream.is_stopped():
                    return self._out_stream
            except Exception:
                pass
            # Stream is dead, recreate
            self._close_output_stream()

        self._pa = pyaudio.PyAudio()
        self._out_stream = self._pa.open(
            format=self._pa.get_format_from_width(2),
            channels=1,
            rate=self._piper_sample_rate,
            output=True,
            output_device_index=self.output_device,
        )
        return self._out_stream

    def _close_output_stream(self):
        """Close the persistent output stream."""
        if self._out_stream is not None:
            try:
                self._out_stream.stop_stream()
                self._out_stream.close()
            except Exception:
                pass
            self._out_stream = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    def speak(self, text: str):
        """Convert text to speech and play it through the speakers (blocks)."""
        if not text:
            return

        logger.debug("Speaking: %s", text[:80])

        if self._use_piper:
            self._speak_piper_sync(text)
        elif self._use_sapi:
            self._speak_sapi(text)

    def speak_async(self, text: str):
        """Start speaking without blocking. Use is_speaking() / stop()."""
        if not text:
            return

        with self._lock:
            self._speaking = True
            self._stop_requested = False

        if self._use_sapi:
            self._speak_sapi_start(text)
        elif self._use_piper:
            self._speech_thread = threading.Thread(
                target=self._speak_piper_async, args=(text,), daemon=True
            )
            self._speech_thread.start()

    def _speak_piper_sync(self, text: str):
        """Speak using Piper TTS (blocking)."""
        try:
            raw_audio = self._synthesize_piper(text)
            if raw_audio:
                self._play_raw_audio(raw_audio)
        except Exception as e:
            logger.error("Piper TTS error: %s", e)

    def _speak_piper_async(self, text: str):
        """Speak using Piper TTS in a background thread (for interrupt support)."""
        try:
            raw_audio = self._synthesize_piper(text)
            if not raw_audio or self._stop_requested:
                return

            self._play_raw_audio_interruptible(raw_audio)
        except Exception as e:
            logger.error("Piper async TTS error: %s", e)
        finally:
            with self._lock:
                self._speaking = False

    def _synthesize_piper(self, text: str) -> bytes | None:
        """Run Piper synthesis and return raw PCM audio bytes."""
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
                return None

            return raw_audio

        except subprocess.TimeoutExpired:
            logger.warning("Speech generation timed out.")
            piper_proc.kill()
            piper_proc.wait()  # Reap zombie process
            return None

    def _speak_sapi(self, text: str):
        """Speak using Windows SAPI — blocks until done or stop() called."""
        self._speak_sapi_start(text)
        self.wait_until_done()

    def _speak_sapi_start(self, text: str):
        """Start speaking asynchronously (returns immediately)."""
        try:
            logger.debug("Speaking out loud: %s", text[:80])

            speaker = self._sapi_speaker
            if speaker is None:
                logger.error("SAPI speaker not initialized.")
                return

            with self._lock:
                self._speaking = True
                self._stop_requested = False

            # Rate: -10 (slow) to 10 (fast), 0 is default
            speaker.Rate = int((self.rate - 1.0) * 5)
            speaker.Volume = 100

            # SVSFlagsAsync = 1, speak without blocking
            speaker.Speak(text, 1)

        except Exception as e:
            with self._lock:
                self._speaking = False
            logger.error("SAPI TTS error: %s", e, exc_info=True)

    def wait_until_done(self):
        """Block until speech finishes or stop() is called."""
        import time
        while self._speaking:
            try:
                done = self._sapi_speaker.WaitUntilDone(50)
                if done:
                    break
            except Exception:
                break
        with self._lock:
            self._speaking = False

    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        if not self._speaking:
            return False

        if self._use_sapi and self._sapi_speaker is not None:
            try:
                done = self._sapi_speaker.WaitUntilDone(0)
                if done:
                    with self._lock:
                        self._speaking = False
                    return False
            except Exception:
                with self._lock:
                    self._speaking = False
                return False

        # For Piper, _speaking is managed by the background thread
        return self._speaking

    def stop(self):
        """Interrupt speech immediately."""
        with self._lock:
            self._stop_requested = True
            self._speaking = False

        if self._use_sapi and self._sapi_speaker is not None:
            try:
                # SVSFPurgeBeforeSpeak = 2, clears the queue and stops
                self._sapi_speaker.Speak("", 2)
            except Exception:
                pass

        logger.info("Speech interrupted.")

    def _play_raw_audio(self, raw_audio: bytes):
        """Play raw PCM audio using the persistent output stream (blocking)."""
        stream = self._get_output_stream()
        chunk_size = 4096
        for i in range(0, len(raw_audio), chunk_size):
            stream.write(raw_audio[i:i + chunk_size])

    def _play_raw_audio_interruptible(self, raw_audio: bytes):
        """Play raw PCM audio in chunks, checking for stop requests between chunks."""
        stream = self._get_output_stream()
        chunk_size = 4096
        for i in range(0, len(raw_audio), chunk_size):
            if self._stop_requested:
                logger.info("Piper speech interrupted during playback.")
                break
            stream.write(raw_audio[i:i + chunk_size])
