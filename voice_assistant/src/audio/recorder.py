"""Audio recorder with voice activity detection (VAD) based on RMS energy."""

import queue
import threading

import numpy as np
import sounddevice as sd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class AudioRecorder:
    """Captures microphone audio, stopping automatically on silence."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        device: int | None = None,
        speech_threshold: float = 0.02,
        silence_duration: float = 1.5,
        max_duration: float = 30.0,
        chunk_duration: float = 0.05,
    ):
        """Initialize the recorder.

        Args:
            sample_rate: Sampling rate in Hz.
            channels: Number of audio channels (must be 1 for Whisper).
            device: Sounddevice input device index. None uses the system default.
            speech_threshold: RMS amplitude above which audio is considered speech.
            silence_duration: Seconds of silence after speech that triggers stop.
            max_duration: Hard cap on recording length in seconds.
            chunk_duration: Size of each audio chunk processed for VAD, in seconds.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.speech_threshold = speech_threshold
        self.silence_duration = silence_duration
        self.max_duration = max_duration
        self.chunk_size = int(chunk_duration * sample_rate)

    def record(self, max_duration: float | None = None) -> np.ndarray:
        """Record from the microphone until silence is detected after speech.

        Waits for speech to begin, then records until the speaker stops.
        Stops automatically after `silence_duration` seconds of silence
        or after `max_duration` seconds regardless.

        Args:
            max_duration: Override for the instance-level max_duration cap.

        Returns:
            1-D float32 numpy array of audio samples at `sample_rate` Hz.
        """
        cap = max_duration if max_duration is not None else self.max_duration
        max_samples = int(cap * self.sample_rate)
        silence_samples = int(self.silence_duration * self.sample_rate)

        audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        stop_event = threading.Event()

        def callback(indata: np.ndarray, frames: int, time, status) -> None:
            if status:
                logger.warning("Audio stream status: %s", status)
            audio_queue.put(indata[:, 0].copy())

        collected: list[np.ndarray] = []
        speech_started = False
        silent_samples = 0
        total_samples = 0

        logger.info("Aguardando fala...")

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.chunk_size,
            device=self.device,
            callback=callback,
        ):
            while not stop_event.is_set():
                try:
                    chunk = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                rms = float(np.sqrt(np.mean(chunk ** 2)))
                is_speech = rms >= self.speech_threshold

                if not speech_started:
                    if is_speech:
                        speech_started = True
                        logger.info("Fala detectada, gravando...")
                    else:
                        continue

                collected.append(chunk)
                total_samples += len(chunk)

                if is_speech:
                    silent_samples = 0
                else:
                    silent_samples += len(chunk)

                if silent_samples >= silence_samples:
                    logger.info("Silencio detectado, encerrando gravacao.")
                    break

                if total_samples >= max_samples:
                    logger.info("Limite maximo de gravacao atingido.")
                    break

        if not collected:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(collected)
        logger.debug("Capturados %d samples (%.1fs).", len(audio), len(audio) / self.sample_rate)
        return audio
