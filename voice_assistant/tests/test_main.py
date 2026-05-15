from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.main import _build_recorder


class MainRecorderConfigTest(unittest.TestCase):
    def test_build_recorder_passes_vad_configuration(self):
        with patch("src.main.AudioRecorder") as recorder_cls:
            _build_recorder(
                {
                    "sample_rate": 16000,
                    "channels": 1,
                    "speech_threshold": 0.03,
                    "silence_duration": 1.1,
                    "max_duration": 12.0,
                    "vad_mode": "webrtc",
                    "vad_aggressiveness": 3,
                    "vad_frame_ms": 20,
                }
            )

        recorder_cls.assert_called_once_with(
            sample_rate=16000,
            channels=1,
            speech_threshold=0.03,
            silence_duration=1.1,
            max_duration=12.0,
            vad_mode="webrtc",
            vad_aggressiveness=3,
            vad_frame_ms=20,
        )


if __name__ == "__main__":
    unittest.main()
