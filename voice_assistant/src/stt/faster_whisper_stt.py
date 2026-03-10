"""Speech-to-Text implementation using Faster Whisper."""

import numpy as np
from faster_whisper import WhisperModel

from src.stt.base_stt import BaseSTT
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FasterWhisperSTT(BaseSTT):
    """STT backend powered by Faster Whisper running on CPU."""

    def __init__(
        self,
        model_size: str = "small",
        compute_type: str = "int8",
        language: str | None = None,
    ):
        """Initialize and load the Whisper model.

        Args:
            model_size: Whisper model variant (e.g. "tiny", "small", "medium").
            compute_type: Quantization type for CPU inference (e.g. "int8", "float32").
            language: BCP-47 language code to force, or None for auto-detection.
        """
        self.language = language
        logger.info("Loading Whisper model '%s' (compute_type=%s)...", model_size, compute_type)
        self._model = WhisperModel(model_size, device="cpu", compute_type=compute_type)
        logger.info("Whisper model loaded.")

    def transcribe(self, audio: np.ndarray) -> str:
        """Convert audio samples to text.

        Args:
            audio: 1-D float32 numpy array at 16 kHz.

        Returns:
            Transcribed text. Empty string if nothing was detected.
        """
        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
        )
        logger.debug("Detected language: %s (%.2f)", info.language, info.language_probability)

        text = " ".join(segment.text.strip() for segment in segments).strip()
        logger.info("Transcription: %s", text or "(empty)")
        return text
