"""TCP server for bash clients.

Protocol (stream-oriented, no extra framing needed):
    Client → Server : raw WAV file bytes  (client closes write end after sending)
    Server → Client : raw WAV file bytes  (server closes connection after sending)

The bash client uses ``nc -N host port < input.wav > output.wav``.
``nc -N`` performs a TCP half-close after stdin EOF, which signals end-of-request
while keeping the read side open to receive the response.
"""

import io
import socket
import wave

import numpy as np

from src.llm.base_llm import BaseLLM
from src.stt.base_stt import BaseSTT
from src.tts.piper_tts import PiperTTS
from src.utils.logger import get_logger
from src.utils.metrics import MetricsLogger, timer

logger = get_logger(__name__)

_RECV_BUF = 65_536


class TCPServer:
    """Accepts WAV audio over TCP, runs STT→LLM→TTS, returns WAV response."""

    def __init__(
        self,
        stt: BaseSTT,
        llm: BaseLLM,
        tts: PiperTTS,
        host: str = "0.0.0.0",
        port: int = 50007,
        metrics_logger: MetricsLogger | None = None,
    ):
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.host = host
        self.port = port
        self.metrics_logger = metrics_logger

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wav_to_float32(wav_bytes: bytes) -> tuple[np.ndarray, int]:
        """Decode WAV bytes to a float32 numpy array.

        Returns:
            Tuple of (float32 audio array, sample_rate).
        """
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            sample_width = wf.getsampwidth()
            pcm = wf.readframes(n_frames)

        if sample_width == 2:
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:
            audio = np.frombuffer(pcm, dtype=np.int32).astype(np.float32) / 2**31
        else:
            raise ValueError(f"Unsupported sample width: {sample_width} bytes")

        return audio, sample_rate

    def _pcm_to_wav(self, pcm_bytes: bytes) -> bytes:
        """Wrap raw int16 PCM bytes in a WAV container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.tts.sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    def _handle(self, conn: socket.socket, addr: tuple) -> None:
        """Process one client connection."""
        metrics = self.metrics_logger.next_turn() if self.metrics_logger else None

        # Read until client closes write end (half-close / full close)
        chunks: list[bytes] = []
        with timer() as t_recv:
            while True:
                chunk = conn.recv(_RECV_BUF)
                if not chunk:
                    break
                chunks.append(chunk)
        wav_bytes = b"".join(chunks)

        if not wav_bytes:
            logger.warning("Empty request from %s, closing.", addr)
            return

        try:
            audio, sample_rate = self._wav_to_float32(wav_bytes)
        except Exception as exc:
            logger.error("Failed to decode WAV from %s: %s", addr, exc)
            return

        if metrics:
            metrics.audio_duration_s = len(audio) / sample_rate
        logger.info("Received %.1fs of audio from %s", len(audio) / sample_rate, addr)

        with timer() as t_stt:
            text = self.stt.transcribe(audio)
        if metrics:
            metrics.stt_latency_s = t_stt[0]
            metrics.transcription = text

        if not text:
            logger.info("No speech detected from %s.", addr)
            return

        logger.info("User said: %s", text)

        with timer() as t_llm:
            response = self.llm.generate(text)
        if metrics:
            metrics.llm_latency_s = t_llm[0]
            metrics.response_chars = len(response)
        logger.info("Assistant: %s", response)

        with timer() as t_tts:
            raw_pcm = self.tts.synthesize_raw(response)
        if metrics:
            metrics.tts_latency_s = t_tts[0]
            if self.metrics_logger:
                self.metrics_logger.log(metrics)

        wav_response = self._pcm_to_wav(raw_pcm)
        conn.sendall(wav_response)
        logger.debug("Sent %d bytes WAV response to %s", len(wav_response), addr)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main server loop – blocks until KeyboardInterrupt."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            srv.listen(1)
            logger.info("TCP server listening on %s:%d (bash client mode)", self.host, self.port)

            try:
                while True:
                    conn, addr = srv.accept()
                    logger.info("Connection from %s", addr)
                    with conn:
                        self._handle(conn, addr)
            except KeyboardInterrupt:
                logger.info("TCP server stopped.")
