"""Speech-to-Text module - listens to the microphone and transcribes speech."""

import logging

import numpy as np
import torch

logger = logging.getLogger(__name__)


class Ears:
    """Captures audio from the microphone and converts speech to text using Whisper.

    The mic stream opens once during initialize() and stays open for the
    entire session. Both listen() and poll_for_speech() use the same stream.

    Optimizations:
    - Pre-allocated numpy buffer and torch tensor to avoid per-chunk allocation
    - VAD state reset between utterances for accurate detection
    """

    def __init__(self, config: dict):
        stt_cfg = config["stt"]
        audio_cfg = config["audio"]
        vad_cfg = config["vad"]

        self.model_name = stt_cfg["model"]
        self.language = stt_cfg.get("language", "en")
        self.device = stt_cfg.get("device", "cpu")
        self.sample_rate = audio_cfg.get("sample_rate", 16000)
        # Silero VAD requires exactly 512 samples at 16kHz (or 256 at 8kHz)
        self.chunk_size = 512 if self.sample_rate == 16000 else 256
        self.input_device = audio_cfg.get("input_device")
        self.silence_threshold = vad_cfg.get("silence_threshold", 1.5)
        self.min_speech_duration = vad_cfg.get("min_speech_duration", 0.5)

        self.whisper_model = None
        self.vad_model = None
        self._pa = None
        self._stream = None
        # Pre-allocated buffers (initialized after we know chunk_size)
        self._chunk_buffer = np.zeros(self.chunk_size, dtype=np.float32)
        self._vad_tensor = torch.zeros(self.chunk_size, dtype=torch.float32)

    def initialize(self):
        """Load Whisper model, VAD model, and open the mic stream."""
        logger.info("Loading Whisper model '%s'...", self.model_name)
        import whisper
        self.whisper_model = whisper.load_model(
            self.model_name, device=self.device
        )
        logger.info("Whisper model loaded.")

        logger.info("Loading Silero VAD model...")
        self.vad_model, self.vad_utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        (
            self.get_speech_timestamps,
            _,
            self.read_audio,
            _,
            _,
        ) = self.vad_utils
        logger.info("VAD model loaded.")

        # Open mic once — stays open for the entire session
        self._open_stream()

    def _open_stream(self):
        """Open a persistent mic stream."""
        import pyaudio

        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            input_device_index=self.input_device,
        )
        logger.info("Mic stream opened (always-on).")

    def shutdown(self):
        """Close the mic stream. Called when Atlas shuts down."""
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
        logger.info("Mic stream closed.")

    def _read_chunk(self):
        """Read one chunk from the always-on mic stream."""
        return self._stream.read(self.chunk_size, exception_on_overflow=False)

    def _vad_probability(self, data: bytes) -> float:
        """Get VAD speech probability for a single audio chunk.

        Reuses pre-allocated numpy buffer and torch tensor to avoid
        per-chunk memory allocation (~31 calls/sec at 16kHz/512).
        """
        int16_data = np.frombuffer(data, dtype=np.int16)
        np.divide(int16_data, 32768.0, out=self._chunk_buffer, casting="unsafe")
        self._vad_tensor.copy_(torch.from_numpy(self._chunk_buffer))
        return self.vad_model(self._vad_tensor, self.sample_rate).item()

    def _transcribe(self, frames: list[bytes]) -> str | None:
        """Transcribe recorded audio frames with Whisper."""
        raw_audio = b"".join(frames)
        audio_np = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0

        duration = len(frames) * self.chunk_size / self.sample_rate
        logger.debug("Transcribing audio (%.2fs)...", duration)

        result = self.whisper_model.transcribe(
            audio_np,
            language=self.language,
            fp16=(self.device == "cuda"),
            initial_prompt="Atlas is a voice assistant. The user speaks to Atlas.",
        )
        text = result["text"].strip()
        return text if text else None

    def listen(self, vad_threshold: float = 0.5) -> str | None:
        """Wait for speech on the always-on mic, record it, and transcribe.

        Blocks until speech is detected and the user stops talking.
        Uses the persistent stream — no open/close overhead.

        Args:
            vad_threshold: VAD probability threshold (default 0.5 for normal listening).
        """
        logger.debug("Listening for speech...")

        # Reset VAD internal state before each new listening session
        self.vad_model.reset_states()

        frames = []
        silent_chunks = 0
        speech_detected = False
        max_silent = int(
            self.silence_threshold * self.sample_rate / self.chunk_size
        )

        try:
            while True:
                data = self._read_chunk()
                speech_prob = self._vad_probability(data)

                if speech_prob > vad_threshold:
                    speech_detected = True
                    silent_chunks = 0
                    frames.append(data)
                elif speech_detected:
                    frames.append(data)
                    silent_chunks += 1
                    if silent_chunks >= max_silent:
                        break
        except KeyboardInterrupt:
            pass

        if not speech_detected or not frames:
            return None

        duration = len(frames) * self.chunk_size / self.sample_rate
        if duration < self.min_speech_duration:
            logger.debug("Speech too short (%.2fs), ignoring.", duration)
            return None

        text = self._transcribe(frames)
        if text:
            logger.info("Heard: %s", text)
        return text

    def poll_for_speech(self, vad_threshold: float = 0.85) -> str | None:
        """Read one chunk from the live mic and check for speech.

        Returns None instantly if no speech in this chunk.
        If speech IS detected, keeps reading until silence, then transcribes.

        Uses the persistent stream — no open/close overhead.

        Args:
            vad_threshold: VAD probability threshold (0.85 = strict, ignores speakers).
        """
        if self._stream is None:
            return None

        try:
            data = self._read_chunk()
        except Exception:
            return None

        speech_prob = self._vad_probability(data)

        if speech_prob <= vad_threshold:
            return None

        # Speech detected — reset VAD state and record until silence
        self.vad_model.reset_states()
        logger.debug("Speech detected (prob=%.2f), recording...", speech_prob)
        frames = [data]
        silent_chunks = 0
        max_silent = int(0.5 * self.sample_rate / self.chunk_size)

        while True:
            try:
                data = self._read_chunk()
            except Exception:
                break

            prob = self._vad_probability(data)
            frames.append(data)

            if prob > 0.5:
                silent_chunks = 0
            else:
                silent_chunks += 1
                if silent_chunks >= max_silent:
                    break

        duration_s = len(frames) * self.chunk_size / self.sample_rate
        if duration_s < 0.3:
            return None

        text = self._transcribe(frames)
        if text:
            logger.info("Interrupt-heard: %s", text)
        return text
