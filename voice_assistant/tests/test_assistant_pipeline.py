from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline.assistant_pipeline import AssistantPipeline


class FakeRecorder:
    sample_rate = 16000

    def record(self):
        return np.ones(3200, dtype=np.float32)


class FakeSTT:
    def transcribe(self, audio):
        return "pode sentar"


class FakeLLM:
    def __init__(self):
        self.calls = []

    def generate(self, prompt: str, conversation_id: str | None = None) -> str:
        self.calls.append((prompt, conversation_id))
        return "Sentando agora."


class FakeTTS:
    def __init__(self):
        self.inputs = []

    def speak(self, text: str) -> None:
        self.inputs.append(text)


class AssistantPipelineCompatibilityTest(unittest.TestCase):
    def test_pipeline_still_consumes_string_response_from_llm(self):
        llm = FakeLLM()
        tts = FakeTTS()
        pipeline = AssistantPipeline(
            recorder=FakeRecorder(),
            stt=FakeSTT(),
            llm=llm,
            tts=tts,
        )

        result = pipeline.run_once()

        self.assertTrue(result)
        self.assertEqual(llm.calls, [("pode sentar", None)])
        self.assertEqual(tts.inputs, ["Sentando agora."])


if __name__ == "__main__":
    unittest.main()
