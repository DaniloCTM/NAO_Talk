"""UDP server: receives audio from a remote client, processes it, streams back TTS audio."""

import socket
import struct
import threading

import numpy as np

from src.llm.base_llm import BaseLLM
from src.network.protocol import (
    AUDIO_DATA,
    AUDIO_END,
    ERROR,
    MAX_CHUNK,
    RESPONSE_DATA,
    RESPONSE_END,
    RESPONSE_META,
    pack,
    unpack,
)
from src.stt.base_stt import BaseSTT
from src.tts.piper_tts import PiperTTS
from src.utils.logger import get_logger
from src.utils.metrics import MetricsLogger, timer

logger = get_logger(__name__)

_RECV_BUF = 65_507  # max UDP payload


def _conversation_id_from_addr(addr: tuple) -> str:
    """Build a stable conversation identifier from a client address."""
    host, port = addr[:2]
    return f"{host}:{port}"


class UDPServer:
    """Listens for audio over UDP, runs STT → LLM → TTS, streams PCM back."""

    def __init__(
        self,
        stt: BaseSTT,
        llm: BaseLLM,
        tts: PiperTTS,
        host: str = "0.0.0.0",
        port: int = 50007,
        audio_sample_rate: int = 16000,
        metrics_logger: MetricsLogger | None = None,
        streaming_enabled: bool = False,
        streaming_min_chunk_s: float = 0.6,
        streaming_update_s: float = 0.3,
    ):
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.host = host
        self.port = port
        self.audio_sample_rate = audio_sample_rate
        self.metrics_logger = metrics_logger
        self.streaming_enabled = streaming_enabled
        self.streaming_min_chunk_s = streaming_min_chunk_s
        self.streaming_update_s = streaming_update_s

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _receive_audio(self, sock: socket.socket) -> tuple[np.ndarray, tuple]:
        """Collect all AUDIO_DATA packets until AUDIO_END.

        Returns:
            Tuple of (float32 audio array, client address).
        """
        chunks: dict[int, bytes] = {}
        client_addr = None

        while True:
            data, addr = sock.recvfrom(_RECV_BUF)
            if client_addr is None:
                client_addr = addr

            try:
                msg_type, seq, payload = unpack(data)
            except ValueError as exc:
                logger.warning("Bad packet from %s: %s", addr, exc)
                continue

            if msg_type == AUDIO_DATA:
                chunks[seq] = payload
            elif msg_type == AUDIO_END:
                break
            else:
                logger.warning("Unexpected packet type %d during audio receive", msg_type)

        if not chunks:
            return np.array([], dtype=np.float32), client_addr

        raw = b"".join(chunks[k] for k in sorted(chunks))
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        logger.debug(
            "Received %d samples (%.1fs) from %s",
            len(audio),
            len(audio) / self.audio_sample_rate,
            client_addr,
        )
        return audio, client_addr

    def _receive_audio_streaming(self, sock: socket.socket) -> tuple[np.ndarray, tuple, str]:
        """Receive live audio and overlap it with partial STT passes."""
        pending: dict[int, bytes] = {}
        raw_buffer = bytearray()
        client_addr = None
        next_seq = 0

        buffer_lock = threading.Lock()
        end_event = threading.Event()
        new_audio_event = threading.Event()

        latest_text = ""
        latest_samples = 0
        transcription_error: Exception | None = None

        min_chunk_samples = int(self.streaming_min_chunk_s * self.audio_sample_rate)
        update_step_samples = int(self.streaming_update_s * self.audio_sample_rate)

        def flush_pending(force: bool = False) -> None:
            nonlocal next_seq
            with buffer_lock:
                while next_seq in pending:
                    raw_buffer.extend(pending.pop(next_seq))
                    next_seq += 1
                    new_audio_event.set()

                if force and pending:
                    for seq in sorted(pending):
                        raw_buffer.extend(pending[seq])
                    pending.clear()
                    new_audio_event.set()

        def transcribe_worker() -> None:
            nonlocal latest_text, latest_samples, transcription_error
            processed_samples = 0

            while not end_event.is_set() or new_audio_event.is_set():
                new_audio_event.wait(timeout=0.1)
                new_audio_event.clear()

                with buffer_lock:
                    sample_count = len(raw_buffer) // 2
                    if sample_count <= processed_samples:
                        continue
                    if sample_count < min_chunk_samples:
                        continue
                    if not end_event.is_set() and (sample_count - processed_samples) < update_step_samples:
                        continue
                    raw_snapshot = bytes(raw_buffer)

                try:
                    audio = np.frombuffer(raw_snapshot, dtype=np.int16).astype(np.float32) / 32768.0
                    text = self.stt.transcribe(audio)
                except Exception as exc:
                    transcription_error = exc
                    end_event.set()
                    return

                latest_text = text
                latest_samples = len(audio)
                processed_samples = len(audio)

        worker = threading.Thread(target=transcribe_worker, daemon=True)
        worker.start()

        while True:
            data, addr = sock.recvfrom(_RECV_BUF)
            if client_addr is None:
                client_addr = addr

            try:
                msg_type, seq, payload = unpack(data)
            except ValueError as exc:
                logger.warning("Bad packet from %s: %s", addr, exc)
                continue

            if msg_type == AUDIO_DATA:
                pending[seq] = payload
                flush_pending()
            elif msg_type == AUDIO_END:
                flush_pending(force=True)
                end_event.set()
                new_audio_event.set()
                break
            else:
                logger.warning("Unexpected packet type %d during audio receive", msg_type)

        worker.join()

        if transcription_error:
            raise transcription_error

        raw = bytes(raw_buffer)
        if not raw:
            return np.array([], dtype=np.float32), client_addr, ""

        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if latest_samples < len(audio):
            latest_text = self.stt.transcribe(audio)

        logger.debug(
            "Received %d samples (%.1fs) from %s with streaming STT",
            len(audio),
            len(audio) / self.audio_sample_rate,
            client_addr,
        )
        return audio, client_addr, latest_text

    def _send_response(
        self, sock: socket.socket, raw_pcm: bytes, client_addr: tuple
    ) -> None:
        """Send RESPONSE_META + RESPONSE_DATA chunks + RESPONSE_END to client."""
        meta = struct.pack("!I", self.tts.sample_rate)
        sock.sendto(pack(RESPONSE_META, 0, meta), client_addr)

        seq = 0
        offset = 0
        while offset < len(raw_pcm):
            chunk = raw_pcm[offset: offset + MAX_CHUNK]
            sock.sendto(pack(RESPONSE_DATA, seq, chunk), client_addr)
            offset += MAX_CHUNK
            seq += 1

        sock.sendto(pack(RESPONSE_END, seq, b""), client_addr)
        logger.debug("Sent %d bytes of audio in %d packets to %s", len(raw_pcm), seq, client_addr)

    def _send_error(self, sock: socket.socket, msg: str, client_addr: tuple) -> None:
        sock.sendto(pack(ERROR, 0, msg.encode("utf-8")), client_addr)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main server loop – blocks until KeyboardInterrupt."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((self.host, self.port))
            logger.info("UDP server listening on %s:%d", self.host, self.port)

            try:
                while True:
                    self._handle_one(sock)
            except KeyboardInterrupt:
                logger.info("UDP server stopped.")

    def _handle_one(self, sock: socket.socket) -> None:
        """Handle one full request/response cycle."""
        metrics = self.metrics_logger.next_turn() if self.metrics_logger else None

        with timer() as t_audio:
            if self.streaming_enabled:
                audio, client_addr, streaming_text = self._receive_audio_streaming(sock)
            else:
                audio, client_addr = self._receive_audio(sock)
                streaming_text = ""

        if audio.size == 0:
            logger.info("Empty audio received, skipping.")
            return

        if metrics:
            metrics.audio_duration_s = len(audio) / self.audio_sample_rate

        logger.info("Processing audio from %s...", client_addr)

        with timer() as t_stt:
            text = streaming_text or self.stt.transcribe(audio)
        if metrics:
            metrics.stt_latency_s = t_stt[0]
            metrics.transcription = text

        if not text:
            logger.info("No speech detected in received audio.")
            self._send_error(sock, "No speech detected.", client_addr)
            return

        logger.info("User said: %s", text)

        with timer() as t_llm:
            response = self.llm.generate(text, conversation_id=_conversation_id_from_addr(client_addr))
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

        self._send_response(sock, raw_pcm, client_addr)
