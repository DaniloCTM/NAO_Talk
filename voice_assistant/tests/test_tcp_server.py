import csv
import io
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import wave

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.network.tcp_server import TCPServer
from src.utils.metrics import MetricsLogger


class FakeSTT:
    def __init__(self):
        self.calls: list[int] = []
        self.started = threading.Event()

    def transcribe(self, audio):
        self.calls.append(len(audio))
        self.started.set()
        return f"text-{len(audio)}"


class FakeLLM:
    def __init__(self):
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"reply:{prompt}"


class FakeTTS:
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self.inputs: list[str] = []
        self.output = (np.array([0, 1000, -1000, 0], dtype=np.int16)).tobytes()

    def synthesize_raw(self, text: str) -> bytes:
        self.inputs.append(text)
        return self.output


class FakeConn:
    def __init__(self):
        self._incoming = bytearray()
        self._outgoing = bytearray()
        self._eof = False
        self._cv = threading.Condition()
        self.sent_event = threading.Event()

    def feed(self, data: bytes) -> None:
        with self._cv:
            self._incoming.extend(data)
            self._cv.notify_all()

    def close_input(self) -> None:
        with self._cv:
            self._eof = True
            self._cv.notify_all()

    def recv(self, bufsize: int) -> bytes:
        with self._cv:
            while not self._incoming and not self._eof:
                self._cv.wait(timeout=0.1)

            if self._incoming:
                data = bytes(self._incoming[:bufsize])
                del self._incoming[:bufsize]
                return data

            return b""

    def sendall(self, data: bytes) -> None:
        self._outgoing.extend(data)
        self.sent_event.set()

    @property
    def sent_bytes(self) -> bytes:
        return bytes(self._outgoing)


class TCPServerTest(unittest.TestCase):
    def _run_handle_in_thread(self, server: TCPServer, conn: FakeConn):
        def target():
            server._handle(conn, ("local", 12345))

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread

    def test_tcp_stream_server_reuses_partial_stt_and_waits_for_eof(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_path = Path(tmpdir) / "metrics.csv"
            stt = FakeSTT()
            llm = FakeLLM()
            tts = FakeTTS()
            server = TCPServer(
                stt=stt,
                llm=llm,
                tts=tts,
                metrics_logger=MetricsLogger(csv_path=metrics_path),
                input_format="pcm_s16le",
                audio_sample_rate=16000,
                streaming_enabled=True,
                streaming_min_chunk_s=0.3,
                streaming_update_s=0.15,
            )

            conn = FakeConn()
            thread = self._run_handle_in_thread(server, conn)
            first_chunk = np.ones(4800, dtype=np.int16).tobytes()
            second_chunk = np.ones(2400, dtype=np.int16).tobytes()

            conn.feed(first_chunk)
            self.assertTrue(stt.started.wait(timeout=1.0))

            self.assertFalse(conn.sent_event.wait(timeout=0.2))

            conn.feed(second_chunk)
            conn.close_input()

            thread.join(timeout=2.0)
            self.assertFalse(thread.is_alive())

            self.assertEqual(stt.calls, [4800, 7200])
            self.assertEqual(llm.prompts, ["text-7200"])
            self.assertEqual(tts.inputs, ["reply:text-7200"])

            with wave.open(io.BytesIO(conn.sent_bytes), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getframerate(), tts.sample_rate)
                self.assertEqual(wf.readframes(wf.getnframes()), tts.output)

            with metrics_path.open("r", newline="") as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["stt_used_partial"], "1")
            self.assertEqual(rows[0]["response_chars"], str(len("reply:text-7200")))

    def test_tcp_server_legacy_wav_mode_still_works(self):
        stt = FakeSTT()
        llm = FakeLLM()
        tts = FakeTTS()
        server = TCPServer(
            stt=stt,
            llm=llm,
            tts=tts,
            input_format="wav",
            audio_sample_rate=16000,
        )

        conn = FakeConn()
        thread = self._run_handle_in_thread(server, conn)
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(np.ones(3200, dtype=np.int16).tobytes())

        conn.feed(wav_buf.getvalue())
        conn.close_input()

        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(stt.calls, [3200])

        with wave.open(io.BytesIO(conn.sent_bytes), "rb") as wf:
            self.assertEqual(wf.getframerate(), tts.sample_rate)


if __name__ == "__main__":
    unittest.main()
