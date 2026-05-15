from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.audio.recorder import AudioRecorder


class FakeVad:
    def __init__(self, aggressiveness: int):
        self.aggressiveness = aggressiveness

    def is_speech(self, pcm_bytes: bytes, sample_rate: int) -> bool:
        del sample_rate
        frame = np.frombuffer(pcm_bytes, dtype=np.int16)
        return bool(frame.size and frame[0] > 0)


class FakeVadModule:
    Vad = FakeVad


class ExplodingVad:
    def __init__(self, aggressiveness: int):
        self.aggressiveness = aggressiveness

    def is_speech(self, pcm_bytes: bytes, sample_rate: int) -> bool:
        del pcm_bytes, sample_rate
        raise RuntimeError("boom")


class ExplodingVadModule:
    Vad = ExplodingVad


class AudioRecorderTest(unittest.TestCase):
    def test_rms_mode_keeps_legacy_detection(self):
        recorder = AudioRecorder(
            sample_rate=16000,
            speech_threshold=0.02,
            silence_duration=0.06,
            chunk_duration=0.02,
            vad_mode="rms",
        )

        chunks = [
            np.zeros(recorder.chunk_size, dtype=np.float32),
            np.full(recorder.chunk_size, 0.10, dtype=np.float32),
            np.full(recorder.chunk_size, 0.10, dtype=np.float32),
            np.zeros(recorder.chunk_size, dtype=np.float32),
            np.zeros(recorder.chunk_size, dtype=np.float32),
            np.zeros(recorder.chunk_size, dtype=np.float32),
        ]

        detected = list(recorder._iter_detected_chunks(iter(chunks)))

        self.assertEqual(len(detected), 5)
        self.assertTrue(np.allclose(detected[0], 0.10))
        self.assertTrue(np.allclose(detected[1], 0.10))

    def test_webrtc_mode_detects_speech_and_keeps_buffered_start(self):
        with patch("src.audio.recorder._webrtcvad", FakeVadModule):
            recorder = AudioRecorder(
                sample_rate=16000,
                silence_duration=0.06,
                vad_mode="webrtc",
                vad_aggressiveness=2,
                vad_frame_ms=20,
            )

        frame_size = recorder.chunk_size
        speech = np.full(frame_size, 0.25, dtype=np.float32)
        silence = np.zeros(frame_size, dtype=np.float32)
        chunks = [silence, speech, speech, speech, silence, silence, silence]

        detected = list(recorder._iter_detected_chunks(iter(chunks)))

        self.assertEqual(recorder.active_vad_mode, "webrtc")
        self.assertEqual(frame_size, 320)
        self.assertEqual(len(detected), 6)
        self.assertTrue(np.allclose(detected[0], speech))
        self.assertTrue(np.allclose(detected[1], speech))

    def test_webrtc_falls_back_to_rms_when_runtime_fails(self):
        with patch("src.audio.recorder._webrtcvad", ExplodingVadModule):
            recorder = AudioRecorder(
                sample_rate=16000,
                speech_threshold=0.02,
                silence_duration=0.06,
                vad_mode="webrtc",
                vad_frame_ms=20,
            )

        speech = np.full(recorder.chunk_size, 0.10, dtype=np.float32)
        silence = np.zeros(recorder.chunk_size, dtype=np.float32)
        chunks = [speech, speech, silence, silence, silence]

        detected = list(recorder._iter_detected_chunks(iter(chunks)))

        self.assertEqual(recorder.active_vad_mode, "rms")
        self.assertEqual(len(detected), 5)
        self.assertTrue(np.allclose(detected[0], speech))

    def test_webrtc_falls_back_to_rms_when_config_invalid(self):
        with patch("src.audio.recorder._webrtcvad", FakeVadModule):
            recorder = AudioRecorder(
                sample_rate=44100,
                vad_mode="webrtc",
                vad_frame_ms=20,
            )

        self.assertEqual(recorder.active_vad_mode, "rms")


if __name__ == "__main__":
    unittest.main()
