"""Latency metrics logger — records timing of each pipeline stage to a CSV file."""

import csv
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

_CSV_PATH = Path("logs/metrics.csv")
_CSV_FIELDNAMES = [
    "timestamp",
    "turn",
    "audio_duration_s",
    "stt_latency_s",
    "llm_latency_s",
    "tts_latency_s",
    "total_latency_s",
    "transcription",
    "response_chars",
]


@dataclass
class TurnMetrics:
    """Timing data for a single pipeline turn."""

    turn: int = 0
    audio_duration_s: float = 0.0
    stt_latency_s: float = 0.0
    llm_latency_s: float = 0.0
    tts_latency_s: float = 0.0
    transcription: str = ""
    response_chars: int = 0

    @property
    def total_latency_s(self) -> float:
        """Sum of STT + LLM + TTS latencies (excludes recording time)."""
        return self.stt_latency_s + self.llm_latency_s + self.tts_latency_s


class MetricsLogger:
    """Appends per-turn latency rows to a CSV file."""

    def __init__(self, csv_path: Path = _CSV_PATH):
        self._path = csv_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._turn = 0

        if not self._path.exists():
            with self._path.open("w", newline="") as f:
                csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES).writeheader()

        logger.info("Metrics will be saved to %s", self._path)

    def log(self, metrics: TurnMetrics) -> None:
        """Append one row to the CSV and print a summary to stdout."""
        row = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "turn": metrics.turn,
            "audio_duration_s": round(metrics.audio_duration_s, 3),
            "stt_latency_s": round(metrics.stt_latency_s, 3),
            "llm_latency_s": round(metrics.llm_latency_s, 3),
            "tts_latency_s": round(metrics.tts_latency_s, 3),
            "total_latency_s": round(metrics.total_latency_s, 3),
            "transcription": metrics.transcription,
            "response_chars": metrics.response_chars,
        }

        with self._path.open("a", newline="") as f:
            csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES).writerow(row)

        logger.info(
            "[Turn %d] audio=%.2fs | STT=%.2fs | LLM=%.2fs | TTS=%.2fs | total=%.2fs",
            metrics.turn,
            metrics.audio_duration_s,
            metrics.stt_latency_s,
            metrics.llm_latency_s,
            metrics.tts_latency_s,
            metrics.total_latency_s,
        )

    def next_turn(self) -> TurnMetrics:
        """Return a fresh TurnMetrics for the next turn, incrementing the counter."""
        self._turn += 1
        return TurnMetrics(turn=self._turn)


@contextmanager
def timer():
    """Context manager that yields a list; list[0] contains elapsed seconds after exit."""
    result = [0.0]
    t0 = time.perf_counter()
    try:
        yield result
    finally:
        result[0] = time.perf_counter() - t0
