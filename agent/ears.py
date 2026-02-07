"""Speech-to-Text module - listens to the microphone and transcribes speech."""

import io
import logging
import tempfile
import wave

import numpy as np

logger = logging.getLogger(__name__)


class Ears:
    """Captures audio from the microphone and converts speech to text using Whisper."""

    def __init__(self, config: dict):
        stt_cfg = config["stt"]
        audio_cfg = config["audio"]
        vad_cfg = config["vad"]

        self.model_name = stt_cfg["model"]
        self.language = stt_cfg.get("language", "en")
        self.device = stt_cfg.get("device", "cpu")
        self.sample_rate = audio_cfg.get("sample_rate", 16000)
        self.chunk_size = audio_cfg.get("chunk_size", 1024)
        self.input_device = audio_cfg.get("input_device")
        self.silence_threshold = vad_cfg.get("silence_threshold", 1.5)
        self.min_speech_duration = vad_cfg.get("min_speech_duration", 0.5)

        self.whisper_model = None
        self.vad_model = None
        self.audio = None

    def initialize(self):
        """Load Whisper model and VAD model."""
        logger.info("Loading Whisper model '%s'...", self.model_name)
        import whisper
        self.whisper_model = whisper.load_model(
            self.model_name, device=self.device
        )
        logger.info("Whisper model loaded.")

        logger.info("Loading Silero VAD model...")
        import torch
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

    def listen(self) -> str | None:
        """
        Listen to the microphone, detect speech, and transcribe it.
        Returns the transcribed text or None if no speech was detected.
        """
        import pyaudio
        import torch

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            input_device_index=self.input_device,
        )

        logger.debug("Listening for speech...")
        frames = []
        silent_chunks = 0
        speech_detected = False
        max_silent = int(
            self.silence_threshold * self.sample_rate / self.chunk_size
        )

        try:
            while True:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                audio_chunk = np.frombuffer(data, dtype=np.int16).astype(
                    np.float32
                )
                audio_chunk /= 32768.0  # Normalize to [-1, 1]

                # Check for voice activity
                tensor = torch.FloatTensor(audio_chunk)
                speech_prob = self.vad_model(tensor, self.sample_rate).item()

                if speech_prob > 0.5:
                    speech_detected = True
                    silent_chunks = 0
                    frames.append(data)
                elif speech_detected:
                    frames.append(data)
                    silent_chunks += 1
                    if silent_chunks >= max_silent:
                        break  # Enough silence after speech, stop recording
        except KeyboardInterrupt:
            pass
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

        if not speech_detected or not frames:
            return None

        # Check minimum duration
        duration = len(frames) * self.chunk_size / self.sample_rate
        if duration < self.min_speech_duration:
            logger.debug("Speech too short (%.2fs), ignoring.", duration)
            return None

        # Write to temporary WAV file for Whisper
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            with wave.open(tmp, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(b"".join(frames))

        # Transcribe
        logger.debug("Transcribing audio (%.2fs)...", duration)
        result = self.whisper_model.transcribe(
            tmp_path,
            language=self.language,
            fp16=(self.device == "cuda"),
        )
        text = result["text"].strip()

        # Clean up temp file
        import os
        os.unlink(tmp_path)

        if text:
            logger.info("Heard: %s", text)
        return text if text else None
