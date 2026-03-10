"""Text-to-Speech implementation using Piper (CLI subprocess)."""

import os
import shutil
import subprocess

import numpy as np
import sounddevice as sd

from src.tts.base_tts import BaseTTS
from src.utils.logger import get_logger

logger = get_logger(__name__)

_ESPEAK_DATA_DEFAULT = "/usr/lib/x86_64-linux-gnu/espeak-ng-data"
_PIPER_LIBS_DEFAULT = "/tmp/piper"


class PiperTTS(BaseTTS):
    """TTS backend that calls the Piper CLI to synthesise Portuguese speech."""

    def __init__(
        self,
        model_path: str = "models/pt_BR-faber-medium.onnx",
        sample_rate: int = 22050,
        espeak_data: str = _ESPEAK_DATA_DEFAULT,
        piper_libs: str = _PIPER_LIBS_DEFAULT,
    ):
        """Initialise the Piper TTS backend.

        Args:
            model_path: Path to the .onnx Piper voice model file.
            sample_rate: Sample rate expected for the chosen model (Hz).
            espeak_data: Path to espeak-ng data directory.
            piper_libs: Directory containing piper shared libraries (.so).

        Raises:
            FileNotFoundError: If the `piper` executable is not on PATH.
        """
        if shutil.which("piper") is None:
            raise FileNotFoundError(
                "The 'piper' executable was not found on PATH. "
                "Install it from https://github.com/rhasspy/piper"
            )

        self.model_path = model_path
        self.sample_rate = sample_rate
        self.espeak_data = espeak_data

        existing = os.environ.get("LD_LIBRARY_PATH", "")
        paths = [p for p in [piper_libs, existing] if p]
        os.environ["LD_LIBRARY_PATH"] = ":".join(paths)

    def _build_cmd(self, extra_flags: list[str]) -> list[str]:
        cmd = ["piper", "--model", self.model_path]
        if self.espeak_data:
            cmd += ["--espeak_data", self.espeak_data]
        return cmd + extra_flags

    def speak(self, text: str) -> None:
        """Synthesise text and play it through the default audio output.

        Args:
            text: Text to be synthesised and spoken aloud.
        """
        if not text.strip():
            return

        logger.info("Synthesising speech...")

        result = subprocess.run(
            self._build_cmd(["--output_raw"]),
            input=text.encode("utf-8"),
            capture_output=True,
            check=True,
        )

        raw_audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32)
        raw_audio /= 32768.0

        logger.debug("Playing synthesised audio (%d samples).", len(raw_audio))
        sd.play(raw_audio, samplerate=self.sample_rate)
        sd.wait()

    def synthesize_raw(self, text: str) -> bytes:
        """Synthesise text and return raw int16 PCM bytes (no playback).

        Args:
            text: Text to be synthesised.

        Returns:
            Raw int16 PCM bytes at ``self.sample_rate`` Hz.
        """
        if not text.strip():
            return b""

        result = subprocess.run(
            self._build_cmd(["--output_raw"]),
            input=text.encode("utf-8"),
            capture_output=True,
            check=True,
        )
        return result.stdout

    def speak_to_file(self, text: str, output_path: str) -> None:
        """Synthesise text and save it as a WAV file.

        Args:
            text: Text to be synthesised.
            output_path: Destination .wav file path.
        """
        subprocess.run(
            self._build_cmd(["--output_file", output_path]),
            input=text.encode("utf-8"),
            check=True,
        )
        logger.info("Audio saved to %s.", output_path)
