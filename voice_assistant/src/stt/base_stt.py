"""Abstract base class for Speech-to-Text backends."""

import numpy as np


class BaseSTT:
    """Interface that all STT implementations must satisfy."""

    def transcribe(self, audio: np.ndarray) -> str:
        """Convert audio samples to text.

        Args:
            audio: 1-D float32 numpy array of audio samples at 16 kHz.

        Returns:
            Transcribed text string. Empty string if nothing was detected.
        """
        raise NotImplementedError
