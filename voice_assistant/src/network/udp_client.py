"""UDP client: records audio locally, sends to server, receives and plays TTS response."""

import socket
import struct

import numpy as np
import sounddevice as sd

from src.audio.recorder import AudioRecorder
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
from src.utils.logger import get_logger

logger = get_logger(__name__)

_RECV_BUF = 65_507
_RECV_TIMEOUT = 10.0  # seconds to wait for server response


class UDPClient:
    """Records audio, streams it to a UDP server, plays the TTS response."""

    def __init__(
        self,
        recorder: AudioRecorder,
        server_host: str,
        server_port: int = 50007,
    ):
        self.recorder = recorder
        self.server_addr = (server_host, server_port)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_audio(self, sock: socket.socket, audio: np.ndarray) -> None:
        """Convert float32 audio to int16 and send in chunks to the server."""
        raw = (audio * 32768.0).clip(-32768, 32767).astype(np.int16).tobytes()

        seq = 0
        offset = 0
        while offset < len(raw):
            chunk = raw[offset: offset + MAX_CHUNK]
            sock.sendto(pack(AUDIO_DATA, seq, chunk), self.server_addr)
            offset += MAX_CHUNK
            seq += 1

        sock.sendto(pack(AUDIO_END, seq, b""), self.server_addr)
        logger.debug("Sent %d bytes of audio in %d packets", len(raw), seq)

    def _receive_response(self, sock: socket.socket) -> tuple[bytes, int]:
        """Collect RESPONSE_DATA packets until RESPONSE_END.

        Returns:
            Tuple of (raw int16 PCM bytes, sample_rate).
        """
        sock.settimeout(_RECV_TIMEOUT)
        chunks: dict[int, bytes] = {}
        sample_rate = 22050  # default, overridden by RESPONSE_META

        try:
            while True:
                data, _ = sock.recvfrom(_RECV_BUF)
                msg_type, seq, payload = unpack(data)

                if msg_type == RESPONSE_META:
                    (sample_rate,) = struct.unpack("!I", payload[:4])
                    logger.debug("Response sample rate: %d Hz", sample_rate)
                elif msg_type == RESPONSE_DATA:
                    chunks[seq] = payload
                elif msg_type == RESPONSE_END:
                    break
                elif msg_type == ERROR:
                    logger.warning("Server error: %s", payload.decode("utf-8", errors="replace"))
                    return b"", sample_rate
                else:
                    logger.warning("Unexpected packet type %d", msg_type)
        except TimeoutError:
            logger.warning("Timed out waiting for server response.")
            return b"", sample_rate
        finally:
            sock.settimeout(None)

        raw = b"".join(chunks[k] for k in sorted(chunks))
        return raw, sample_rate

    def _play(self, raw_pcm: bytes, sample_rate: int) -> None:
        """Play raw int16 PCM bytes through the default audio output."""
        if not raw_pcm:
            return
        audio = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        logger.debug("Playing %d samples at %d Hz", len(audio), sample_rate)
        sd.play(audio, samplerate=sample_rate)
        sd.wait()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_once(self) -> bool:
        """Execute one record → send → receive → play cycle.

        Returns:
            True if a full cycle completed, False if no speech was captured.
        """
        audio = self.recorder.record()
        if audio.size == 0:
            logger.info("No speech detected, skipping.")
            return False

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            self._send_audio(sock, audio)
            logger.info("Audio sent to server %s, waiting for response...", self.server_addr)
            raw_pcm, sample_rate = self._receive_response(sock)

        self._play(raw_pcm, sample_rate)
        return True

    def run(self) -> None:
        """Run the client in an infinite loop until interrupted."""
        logger.info(
            "UDP client started. Server: %s:%d  Press Ctrl+C to stop.",
            *self.server_addr,
        )
        try:
            while True:
                self.run_once()
        except KeyboardInterrupt:
            logger.info("UDP client stopped.")
