"""Audio recorder with configurable voice activity detection."""

from collections import deque
import queue

import numpy as np
import sounddevice as sd

from src.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import webrtcvad as _webrtcvad
except ImportError:  # pragma: no cover - exercised through fallback behavior
    _webrtcvad = None

_SUPPORTED_WEBRTC_SAMPLE_RATES = {8000, 16000, 32000, 48000}
_SUPPORTED_WEBRTC_FRAME_MS = {10, 20, 30}
_DEFAULT_WEBRTC_START_FRAMES = 2


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
        vad_mode: str = "webrtc",
        vad_aggressiveness: int = 2,
        vad_frame_ms: int = 30,
    ):
        """Initialize the recorder.

        Args:
            sample_rate: Sampling rate in Hz.
            channels: Number of audio channels (must be 1 for Whisper).
            device: Sounddevice input device index. None uses the system default.
            speech_threshold: RMS amplitude above which audio is considered speech in `rms` mode.
            silence_duration: Seconds of silence after speech that triggers stop.
            max_duration: Hard cap on recording length in seconds.
            chunk_duration: Size of each audio chunk processed in `rms` mode, in seconds.
            vad_mode: Preferred VAD backend. `webrtc` is recommended; `rms` is the legacy fallback.
            vad_aggressiveness: WebRTC VAD aggressiveness level from 0 to 3.
            vad_frame_ms: WebRTC frame size in milliseconds. Must be 10, 20 or 30.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.speech_threshold = speech_threshold
        self.silence_duration = silence_duration
        self.max_duration = max_duration
        self.chunk_duration = chunk_duration
        self.vad_mode = vad_mode
        self.vad_aggressiveness = vad_aggressiveness
        self.vad_frame_ms = vad_frame_ms
        self._webrtc_start_frames = _DEFAULT_WEBRTC_START_FRAMES
        self._webrtc_vad = None
        self.active_vad_mode = "rms"
        self.chunk_size = max(1, int(chunk_duration * sample_rate))
        self._configure_vad_mode()

    def record_stream(self, max_duration: float | None = None):
        """Yield chunks from the microphone until silence ends the utterance."""
        audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        logger.info("Aguardando fala...")

        def callback(indata: np.ndarray, frames: int, time, status) -> None:
            del frames, time
            if status:
                logger.warning("Audio stream status: %s", status)
            audio_queue.put(indata[:, 0].copy())

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.chunk_size,
            device=self.device,
            callback=callback,
        ):
            yield from self._iter_detected_chunks(self._microphone_chunks(audio_queue), max_duration=max_duration)

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
        collected = list(self.record_stream(max_duration=max_duration))

        if not collected:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(collected)
        return audio

    def _configure_vad_mode(self) -> None:
        """Choose the active VAD mode and recorder block size."""
        requested_mode = str(self.vad_mode).strip().lower()
        if requested_mode == "webrtc":
            error = self._validate_webrtc_config()
            if error:
                logger.warning("WebRTC VAD unavailable (%s). Falling back to RMS VAD.", error)
                self.active_vad_mode = "rms"
                self.chunk_size = max(1, int(self.chunk_duration * self.sample_rate))
                return

            self._webrtc_vad = _webrtcvad.Vad(self.vad_aggressiveness)
            self.active_vad_mode = "webrtc"
            self.chunk_size = int(self.sample_rate * self.vad_frame_ms / 1000)
            logger.info(
                "AudioRecorder using WebRTC VAD (aggressiveness=%d, frame=%dms).",
                self.vad_aggressiveness,
                self.vad_frame_ms,
            )
            return

        if requested_mode != "rms":
            logger.warning("Unknown VAD mode '%s'. Falling back to RMS VAD.", self.vad_mode)

        self.active_vad_mode = "rms"
        self.chunk_size = max(1, int(self.chunk_duration * self.sample_rate))

    def _validate_webrtc_config(self) -> str | None:
        """Return an error string if WebRTC VAD cannot be used."""
        if _webrtcvad is None:
            return "dependency not installed"
        if self.channels != 1:
            return "WebRTC VAD requires mono audio"
        if self.sample_rate not in _SUPPORTED_WEBRTC_SAMPLE_RATES:
            return f"sample_rate {self.sample_rate} unsupported"
        if self.vad_frame_ms not in _SUPPORTED_WEBRTC_FRAME_MS:
            return f"vad_frame_ms {self.vad_frame_ms} unsupported"
        if self.vad_aggressiveness not in {0, 1, 2, 3}:
            return f"vad_aggressiveness {self.vad_aggressiveness} unsupported"
        return None

    def _microphone_chunks(self, audio_queue: queue.Queue[np.ndarray]):
        """Yield chunks captured asynchronously from the microphone callback."""
        while True:
            try:
                yield audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

    def _iter_detected_chunks(self, chunks, max_duration: float | None = None):
        """Yield only the speech segment detected from an input chunk iterator."""
        cap = max_duration if max_duration is not None else self.max_duration
        max_samples = int(cap * self.sample_rate)
        silence_samples = int(self.silence_duration * self.sample_rate)

        if self.active_vad_mode == "webrtc":
            yield from self._iter_detected_chunks_webrtc(chunks, max_samples, silence_samples)
        else:
            yield from self._iter_detected_chunks_rms(chunks, max_samples, silence_samples)

    def _iter_detected_chunks_rms(self, chunks, max_samples: int, silence_samples: int):
        """Legacy RMS-based VAD pipeline."""
        speech_started = False
        silent_samples = 0
        total_samples = 0

        for chunk in chunks:
            is_speech = self._is_speech_rms(chunk)

            if not speech_started:
                if is_speech:
                    speech_started = True
                    logger.info("Fala detectada, gravando...")
                else:
                    continue

            total_samples += len(chunk)

            if is_speech:
                silent_samples = 0
            else:
                silent_samples += len(chunk)

            yield chunk

            if silent_samples >= silence_samples:
                logger.info("Silencio detectado, encerrando gravacao.")
                break

            if total_samples >= max_samples:
                logger.info("Limite maximo de gravacao atingido.")
                break

        logger.debug("Capturados %d samples (%.1fs).", total_samples, total_samples / self.sample_rate)

    def _iter_detected_chunks_webrtc(self, chunks, max_samples: int, silence_samples: int):
        """WebRTC-VAD-based pipeline with a short speech start buffer."""
        speech_started = False
        speech_frames = 0
        silent_samples = 0
        total_samples = 0
        pending_chunks: deque[np.ndarray] = deque(maxlen=self._webrtc_start_frames)

        for chunk in chunks:
            pending_chunks.append(chunk)
            is_speech = self._is_speech_webrtc(chunk)

            if not speech_started:
                if is_speech:
                    speech_frames += 1
                    if speech_frames >= self._webrtc_start_frames:
                        speech_started = True
                        logger.info("Fala detectada, gravando...")
                        while pending_chunks:
                            buffered_chunk = pending_chunks.popleft()
                            total_samples += len(buffered_chunk)
                            yield buffered_chunk
                else:
                    speech_frames = 0
                    pending_chunks.clear()
                continue

            total_samples += len(chunk)

            if is_speech:
                silent_samples = 0
            else:
                silent_samples += len(chunk)

            yield chunk

            if silent_samples >= silence_samples:
                logger.info("Silencio detectado, encerrando gravacao.")
                break

            if total_samples >= max_samples:
                logger.info("Limite maximo de gravacao atingido.")
                break

        logger.debug("Capturados %d samples (%.1fs).", total_samples, total_samples / self.sample_rate)

    def _is_speech_rms(self, chunk: np.ndarray) -> bool:
        """Decide speech using RMS amplitude."""
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        return rms >= self.speech_threshold

    def _is_speech_webrtc(self, chunk: np.ndarray) -> bool:
        """Decide speech using WebRTC VAD, with automatic fallback to RMS on errors."""
        if self._webrtc_vad is None:
            self._fallback_to_rms("WebRTC VAD not initialised")
            return self._is_speech_rms(chunk)

        try:
            pcm16 = np.clip(chunk * 32768.0, -32768, 32767).astype(np.int16)
            return bool(self._webrtc_vad.is_speech(pcm16.tobytes(), self.sample_rate))
        except Exception as exc:  # pragma: no cover - exercised via tests through fallback branch
            self._fallback_to_rms(f"runtime error: {exc}")
            return self._is_speech_rms(chunk)

    def _fallback_to_rms(self, reason: str) -> None:
        """Switch to RMS mode after a WebRTC failure."""
        if self.active_vad_mode == "rms":
            return

        logger.warning("Falling back to RMS VAD after WebRTC failure: %s", reason)
        self.active_vad_mode = "rms"
        self._webrtc_vad = None
