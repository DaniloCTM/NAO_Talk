"""Latency metrics logger — records timing of each pipeline stage to a CSV file."""

import csv
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

_CSV_PATH = Path("logs/metrics.csv")
_CSV_FIELDNAMES = [
    "timestamp",
    "turn",
    "audio_duration_s",
    "receive_wall_s",
    "stt_latency_s",
    "llm_latency_s",
    "tts_latency_s",
    "total_latency_s",
    "post_receive_to_response_s",
    "stt_used_partial",
    "transcription",
    "response_chars",
]


@dataclass
class TurnMetrics:
    """Timing data for a single pipeline turn."""

    turn: int = 0
    audio_duration_s: float = 0.0
    receive_wall_s: float = 0.0
    stt_latency_s: float = 0.0
    llm_latency_s: float = 0.0
    tts_latency_s: float = 0.0
    post_receive_to_response_s: float = 0.0
    stt_used_partial: bool = False
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

        self._ensure_header()

        logger.info("Metrics will be saved to %s", self._path)

    def _ensure_header(self) -> None:
        """Ensure the metrics CSV header matches the current schema."""
        expected_header = ",".join(_CSV_FIELDNAMES)

        if not self._path.exists():
            with self._path.open("w", newline="") as f:
                csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES).writeheader()
            return

        with self._path.open("r", newline="") as f:
            current_header = f.readline().strip()

        if current_header == expected_header:
            return

        backup_name = f"{self._path.name}.bak.{time.strftime('%Y%m%d%H%M%S')}"
        backup_path = self._path.with_name(backup_name)
        self._path.rename(backup_path)
        logger.warning("Metrics schema changed; previous CSV moved to %s", backup_path)

        with self._path.open("w", newline="") as f:
            csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES).writeheader()

    def log(self, metrics: TurnMetrics) -> None:
        """Append one row to the CSV and print a summary to stdout."""
        row = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "turn": metrics.turn,
            "audio_duration_s": round(metrics.audio_duration_s, 3),
            "receive_wall_s": round(metrics.receive_wall_s, 3),
            "stt_latency_s": round(metrics.stt_latency_s, 3),
            "llm_latency_s": round(metrics.llm_latency_s, 3),
            "tts_latency_s": round(metrics.tts_latency_s, 3),
            "total_latency_s": round(metrics.total_latency_s, 3),
            "post_receive_to_response_s": round(metrics.post_receive_to_response_s, 3),
            "stt_used_partial": int(metrics.stt_used_partial),
            "transcription": metrics.transcription,
            "response_chars": metrics.response_chars,
        }

        with self._path.open("a", newline="") as f:
            csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES).writerow(row)

        logger.info(
            "[Turn %d] audio=%.2fs | recv=%.2fs | STT=%.2fs | LLM=%.2fs | TTS=%.2fs | post=%.2fs | partial=%s | total=%.2fs",
            metrics.turn,
            metrics.audio_duration_s,
            metrics.receive_wall_s,
            metrics.stt_latency_s,
            metrics.llm_latency_s,
            metrics.tts_latency_s,
            metrics.post_receive_to_response_s,
            "yes" if metrics.stt_used_partial else "no",
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
