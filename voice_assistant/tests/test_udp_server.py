from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.network.udp_server import UDPServer


class FakeSTT:
    def transcribe(self, audio):
        return "fala udp"


class FakeLLM:
    def __init__(self):
        self.calls: list[tuple[str, str | None]] = []

    def generate(self, prompt: str, conversation_id: str | None = None) -> str:
        self.calls.append((prompt, conversation_id))
        return "resposta udp"


class FakeTTS:
    sample_rate = 22050

    def __init__(self):
        self.inputs: list[str] = []

    def synthesize_raw(self, text: str) -> bytes:
        self.inputs.append(text)
        return (np.array([0, 1000, -1000, 0], dtype=np.int16)).tobytes()


class UDPServerConversationTest(unittest.TestCase):
    def test_udp_server_passes_conversation_id_from_client_addr(self):
        llm = FakeLLM()
        tts = FakeTTS()
        server = UDPServer(
            stt=FakeSTT(),
            llm=llm,
            tts=tts,
            audio_sample_rate=16000,
        )

        server._receive_audio = lambda sock: (np.ones(3200, dtype=np.float32), ("127.0.0.1", 45678))
        sent_payloads: list[tuple[bytes, tuple]] = []
        server._send_response = lambda sock, raw_pcm, client_addr: sent_payloads.append((raw_pcm, client_addr))

        class DummySock:
            pass

        server._handle_one(DummySock())

        self.assertEqual(llm.calls, [("fala udp", "127.0.0.1:45678")])
        self.assertEqual(tts.inputs, ["resposta udp"])
        self.assertEqual(sent_payloads[0][1], ("127.0.0.1", 45678))


if __name__ == "__main__":
    unittest.main()
