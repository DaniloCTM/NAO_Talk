"""Audio player using sounddevice."""

import numpy as np
import sounddevice as sd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AudioPlayer:
    """Plays audio arrays through the system's output device."""

    def __init__(self, device: int | None = None):
        """Initialize the player.

        Args:
            device: Sounddevice output device index. None uses the system default.
        """
        self.device = device

    def play(self, audio: np.ndarray, sample_rate: int) -> None:
        """Play an audio array.

        Args:
            audio: 1-D or 2-D numpy array of audio samples.
            sample_rate: Sampling rate in Hz.
        """
        logger.debug("Playing %d samples at %d Hz.", len(audio), sample_rate)
        sd.play(audio, samplerate=sample_rate, device=self.device)
        sd.wait()
