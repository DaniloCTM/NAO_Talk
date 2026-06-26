"""TCP server for shell-based clients.

Supported request formats:
    Legacy TCP mode:
        Client → Server : raw WAV file bytes
    Streaming TCP mode:
        Client → Server : raw PCM S16_LE mono 16 kHz bytes

For both modes:
    Server → Client : raw WAV file bytes

The shell client uses ``nc -N host port`` so it can half-close the socket after
request EOF while still reading the WAV response from the server.
"""

import io
import json
from dataclasses import dataclass
from pathlib import Path
import socket
from tempfile import NamedTemporaryFile
import threading
import wave

import numpy as np

from src.llm.base_llm import BaseLLM
from src.stt.base_stt import BaseSTT
from src.tts.piper_tts import PiperTTS
from src.utils.logger import get_logger
from src.utils.metrics import MetricsLogger, timer

logger = get_logger(__name__)

_RECV_BUF = 65_536
_DEBUG_AUDIO_DIR = Path("/tmp")
_PCM_SAMPLE_WIDTH_BYTES = 2
_METADATA_MAGIC = b"VA1\n"
_METADATA_SEPARATOR = b"\n\n"
_MAX_METADATA_BYTES = 8_192


def _conversation_id_from_addr(addr: tuple) -> str:
    """Build a stable conversation identifier from a client address."""
    host, port = addr[:2]
    return f"{host}:{port}"


@dataclass
class _RequestAudio:
    """Decoded request payload plus metadata needed by the pipeline."""

    raw_bytes: bytes
    audio: np.ndarray
    sample_rate: int
    debug_suffix: str
    partial_text: str = ""
    stt_used_partial: bool = False
    metadata: dict | None = None


class TCPServer:
    """Accepts shell client audio over TCP and returns a WAV response."""

    def __init__(
        self,
        stt: BaseSTT,
        llm: BaseLLM,
        tts: PiperTTS,
        host: str = "0.0.0.0",
        port: int = 50007,
        metrics_logger: MetricsLogger | None = None,
        input_format: str = "wav",
        audio_sample_rate: int = 16000,
        streaming_enabled: bool = False,
        streaming_min_chunk_s: float = 0.3,
        streaming_update_s: float = 0.15,
    ):
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.host = host
        self.port = port
        self.metrics_logger = metrics_logger
        self.input_format = input_format
        self.audio_sample_rate = audio_sample_rate
        self.streaming_enabled = streaming_enabled
        self.streaming_min_chunk_s = streaming_min_chunk_s
        self.streaming_update_s = streaming_update_s

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wav_to_float32(wav_bytes: bytes) -> tuple[np.ndarray, int]:
        """Decode WAV bytes to a float32 numpy array."""
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

    @staticmethod
    def _pcm16_to_float32(raw_bytes: bytes) -> np.ndarray:
        """Decode raw signed 16-bit PCM bytes to float32 mono audio."""
        usable = len(raw_bytes) - (len(raw_bytes) % _PCM_SAMPLE_WIDTH_BYTES)
        if usable <= 0:
            return np.array([], dtype=np.float32)
        return np.frombuffer(raw_bytes[:usable], dtype=np.int16).astype(np.float32) / 32768.0

    def _pcm_to_wav(self, pcm_bytes: bytes) -> bytes:
        """Wrap raw int16 PCM bytes in a WAV container."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.tts.sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    @staticmethod
    def _save_debug_request(raw_bytes: bytes, addr: tuple, suffix: str) -> Path:
        """Persist the raw request bytes to /tmp for offline inspection."""
        host, port = addr[:2]
        host_tag = str(host).replace(":", "_")
        _DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(
            mode="wb",
            prefix=f"nao_input_{host_tag}_{port}_",
            suffix=suffix,
            dir=_DEBUG_AUDIO_DIR,
            delete=False,
        ) as tmp_file:
            tmp_file.write(raw_bytes)
            return Path(tmp_file.name)

    @staticmethod
    def _read_all(conn: socket.socket) -> bytes:
        """Read the full request until the client half-closes the socket."""
        chunks: list[bytes] = []
        while True:
            chunk = conn.recv(_RECV_BUF)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _extract_metadata_prefix(raw_bytes: bytes) -> tuple[dict | None, bytes]:
        """Extract an optional JSON metadata preamble from the request bytes."""
        if not raw_bytes.startswith(_METADATA_MAGIC):
            return None, raw_bytes

        separator_index = raw_bytes.find(_METADATA_SEPARATOR, len(_METADATA_MAGIC))
        if separator_index == -1:
            raise ValueError("Incomplete metadata preamble received from client.")

        metadata_bytes = raw_bytes[len(_METADATA_MAGIC):separator_index]
        if len(metadata_bytes) > _MAX_METADATA_BYTES:
            raise ValueError("Metadata preamble exceeds supported size.")

        metadata = json.loads(metadata_bytes.decode("utf-8"))
        payload = raw_bytes[separator_index + len(_METADATA_SEPARATOR):]
        return metadata, payload

    def _receive_wav_request(self, conn: socket.socket) -> _RequestAudio:
        """Receive a legacy WAV request."""
        raw_request = self._read_all(conn)
        metadata, wav_bytes = self._extract_metadata_prefix(raw_request)
        if not wav_bytes:
            return _RequestAudio(
                b"",
                np.array([], dtype=np.float32),
                self.audio_sample_rate,
                ".wav",
                metadata=metadata,
            )

        audio, sample_rate = self._wav_to_float32(wav_bytes)
        return _RequestAudio(wav_bytes, audio, sample_rate, ".wav", metadata=metadata)

    def _receive_pcm_request(self, conn: socket.socket) -> _RequestAudio:
        """Receive a raw PCM request, optionally overlapping partial STT."""
        if not self.streaming_enabled:
            raw_request = self._read_all(conn)
            metadata, raw_bytes = self._extract_metadata_prefix(raw_request)
            audio = self._pcm16_to_float32(raw_bytes)
            return _RequestAudio(
                raw_bytes,
                audio,
                self.audio_sample_rate,
                ".s16le",
                metadata=metadata,
            )

        raw_buffer = bytearray()
        buffer_lock = threading.Lock()
        end_event = threading.Event()
        new_audio_event = threading.Event()

        latest_text = ""
        latest_samples = 0
        transcription_error: Exception | None = None
        metadata: dict | None = None
        metadata_parsed = False
        preamble_buffer = bytearray()

        min_chunk_samples = max(1, int(self.streaming_min_chunk_s * self.audio_sample_rate))
        update_step_samples = max(1, int(self.streaming_update_s * self.audio_sample_rate))

        def snapshot_locked() -> tuple[bytes, int]:
            usable = len(raw_buffer) - (len(raw_buffer) % _PCM_SAMPLE_WIDTH_BYTES)
            if usable <= 0:
                return b"", 0
            return bytes(raw_buffer[:usable]), usable // _PCM_SAMPLE_WIDTH_BYTES

        def transcribe_worker() -> None:
            nonlocal latest_text, latest_samples, transcription_error
            processed_samples = 0

            while not end_event.is_set() or new_audio_event.is_set():
                new_audio_event.wait(timeout=0.05)
                new_audio_event.clear()

                with buffer_lock:
                    raw_snapshot, sample_count = snapshot_locked()

                if sample_count <= processed_samples:
                    continue
                if sample_count < min_chunk_samples:
                    continue
                if not end_event.is_set() and (sample_count - processed_samples) < update_step_samples:
                    continue

                try:
                    audio = self._pcm16_to_float32(raw_snapshot)
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
            chunk = conn.recv(_RECV_BUF)
            if not chunk:
                break
            if not metadata_parsed:
                preamble_buffer.extend(chunk)
                if len(preamble_buffer) >= len(_METADATA_MAGIC) and not preamble_buffer.startswith(_METADATA_MAGIC):
                    with buffer_lock:
                        raw_buffer.extend(preamble_buffer)
                    preamble_buffer.clear()
                    metadata_parsed = True
                    new_audio_event.set()
                    continue

                separator_index = preamble_buffer.find(_METADATA_SEPARATOR, len(_METADATA_MAGIC))
                if separator_index != -1:
                    metadata, payload = self._extract_metadata_prefix(bytes(preamble_buffer))
                    with buffer_lock:
                        raw_buffer.extend(payload)
                    preamble_buffer.clear()
                    metadata_parsed = True
                    new_audio_event.set()
                    continue

                if len(preamble_buffer) > _MAX_METADATA_BYTES + len(_METADATA_MAGIC) + len(_METADATA_SEPARATOR):
                    raise ValueError("Metadata preamble exceeds supported size.")
                continue

            with buffer_lock:
                raw_buffer.extend(chunk)
            new_audio_event.set()

        if not metadata_parsed and preamble_buffer:
            if preamble_buffer.startswith(_METADATA_MAGIC):
                metadata, raw_bytes = self._extract_metadata_prefix(bytes(preamble_buffer))
            else:
                metadata, raw_bytes = None, bytes(preamble_buffer)
            with buffer_lock:
                raw_buffer.extend(raw_bytes)

        end_event.set()
        new_audio_event.set()
        worker.join()

        if transcription_error:
            raise transcription_error

        with buffer_lock:
            raw_snapshot, _ = snapshot_locked()

        audio = self._pcm16_to_float32(raw_snapshot)
        stt_used_partial = bool(latest_text) and latest_samples == len(audio)
        partial_text = latest_text if stt_used_partial else ""

        return _RequestAudio(
            raw_snapshot,
            audio,
            self.audio_sample_rate,
            ".s16le",
            partial_text=partial_text,
            stt_used_partial=stt_used_partial,
            metadata=metadata,
        )

    def _receive_request(self, conn: socket.socket) -> _RequestAudio:
        """Receive one full request according to the configured input format."""
        if self.input_format == "wav":
            return self._receive_wav_request(conn)
        if self.input_format == "pcm_s16le":
            return self._receive_pcm_request(conn)
        raise ValueError(f"Unsupported TCP input format: {self.input_format}")

    def _handle(self, conn: socket.socket, addr: tuple) -> None:
        """Process one client connection."""
        metrics = self.metrics_logger.next_turn() if self.metrics_logger else None

        with timer() as t_recv:
            try:
                request = self._receive_request(conn)
            except Exception as exc:
                logger.error("Failed to decode request from %s: %s", addr, exc)
                return

        if not request.raw_bytes or request.audio.size == 0:
            logger.warning("Empty request from %s, closing.", addr)
            return

        debug_path = self._save_debug_request(request.raw_bytes, addr, request.debug_suffix)
        logger.info("Saved incoming request from %s to %s", addr, debug_path)
        if request.metadata is not None:
            logger.info("Received client metadata from %s: %s", addr, request.metadata)
        else:
            logger.warning("No client metadata received from %s.", addr)

        if metrics:
            metrics.audio_duration_s = len(request.audio) / request.sample_rate
            metrics.receive_wall_s = t_recv[0]

        logger.info("Received %.1fs of audio from %s", len(request.audio) / request.sample_rate, addr)

        text = ""
        with timer() as t_post:
            with timer() as t_stt:
                text = request.partial_text or self.stt.transcribe(request.audio)
            if metrics:
                metrics.stt_latency_s = t_stt[0]
                metrics.transcription = text
                metrics.stt_used_partial = request.stt_used_partial

            if text:
                logger.info("User said: %s", text)

                with timer() as t_llm:
                    try:
                        response = self.llm.generate(
                            text,
                            conversation_id=_conversation_id_from_addr(addr),
                        )
                    except Exception as exc:
                        logger.exception("LLM generation failed for %s: %s", addr, exc)
                        response = "Desculpe, ocorreu um erro ao processar sua solicitação."
                if metrics:
                    metrics.llm_latency_s = t_llm[0]
                    metrics.response_chars = len(response)
                logger.info("Assistant: %s", response)

                with timer() as t_tts:
                    raw_pcm = self.tts.synthesize_raw(response)
                if metrics:
                    metrics.tts_latency_s = t_tts[0]

                wav_response = self._pcm_to_wav(raw_pcm)
                conn.sendall(wav_response)
                logger.debug("Sent %d bytes WAV response to %s", len(wav_response), addr)
            else:
                logger.info("No speech detected from %s.", addr)

        if metrics:
            metrics.post_receive_to_response_s = t_post[0]
            if self.metrics_logger:
                self.metrics_logger.log(metrics)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main server loop – blocks until KeyboardInterrupt."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            srv.listen(1)
            logger.info(
                "TCP server listening on %s:%d (input=%s, streaming_stt=%s)",
                self.host,
                self.port,
                self.input_format,
                self.streaming_enabled,
            )

            try:
                while True:
                    conn, addr = srv.accept()
                    logger.info("Connection from %s", addr)
                    with conn:
                        self._handle(conn, addr)
            except KeyboardInterrupt:
                logger.info("TCP server stopped.")
