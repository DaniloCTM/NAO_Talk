#!/usr/bin/env python3
"""Evaluate STT latency and transcriptions over dataset_teste and inject into the Markdown report."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
import re
import statistics
import sys
import time
import wave

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.stt.faster_whisper_stt import FasterWhisperSTT
from src.utils.config_loader import load_config

SECTION_START = "<!-- STT_SECTION_START -->"
SECTION_END = "<!-- STT_SECTION_END -->"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate STT metrics over dataset_teste.")
    parser.add_argument(
        "--dataset-dir",
        default=str(PROJECT_ROOT / "dataset_teste"),
        help="Dataset directory containing manifest.csv.",
    )
    parser.add_argument(
        "--report",
        default=str(PROJECT_ROOT / "dataset_teste" / "relatorio_metricas_llm_tts.md"),
        help="Markdown report to update with an STT section.",
    )
    parser.add_argument(
        "--results-csv",
        default=str(PROJECT_ROOT / "dataset_teste" / "resultados_metricas_stt.csv"),
        help="Output CSV with per-sample STT results.",
    )
    return parser.parse_args()


def load_manifest(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def load_wav_float32(audio_path: Path) -> np.ndarray:
    with wave.open(str(audio_path), "rb") as wav_file:
        sample_width = wav_file.getsampwidth()
        channels = wav_file.getnchannels()
        frames = wav_file.readframes(wav_file.getnframes())

    if sample_width != 2:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {key: 0.0 for key in ("mean", "median", "p95", "min", "max")}
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "p95": percentile(values, 0.95),
        "min": min(values),
        "max": max(values),
    }


def normalize_text(text: str) -> str:
    normalized = text.casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def exact_match(expected: str, transcription: str) -> bool:
    return normalize_text(expected) == normalize_text(transcription)


def fmt(value: float) -> str:
    return f"{value:.3f}"


def write_results_csv(results_path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "categoria",
        "frase_esperada",
        "transcricao_stt",
        "exact_match",
        "stt_latency_s",
        "audio_duration_s",
        "audio_path",
    ]
    with results_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_stt_section(results: list[dict[str, object]], stt_model: str, compute_type: str) -> str:
    latencies = [float(row["stt_latency_s"]) for row in results]
    durations = [float(row["audio_duration_s"]) for row in results]
    exact_hits = sum(1 for row in results if row["exact_match"] is True)
    exact_rate = (exact_hits / len(results) * 100.0) if results else 0.0
    latency_summary = summarize(latencies)
    duration_summary = summarize(durations)

    lines: list[str] = []
    lines.append(SECTION_START)
    lines.append("## STT")
    lines.append("")
    lines.append(f"- Gerado em: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- Modelo STT: `{stt_model}`")
    lines.append(f"- Compute type: `{compute_type}`")
    lines.append("")
    lines.append("### Resumo")
    lines.append("")
    lines.append("| Métrica | Média | Mediana | P95 | Mín | Máx |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    lines.append(
        f"| STT latency (s) | {fmt(latency_summary['mean'])} | {fmt(latency_summary['median'])} | {fmt(latency_summary['p95'])} | {fmt(latency_summary['min'])} | {fmt(latency_summary['max'])} |"
    )
    lines.append(
        f"| Duração do áudio (s) | {fmt(duration_summary['mean'])} | {fmt(duration_summary['median'])} | {fmt(duration_summary['p95'])} | {fmt(duration_summary['min'])} | {fmt(duration_summary['max'])} |"
    )
    lines.append("")
    lines.append(f"- Exact match normalizado: `{exact_hits}/{len(results)}` (`{exact_rate:.1f}%`)")
    lines.append("")
    lines.append("### Resultados por amostra")
    lines.append("")
    lines.append("| ID | Categoria | Frase esperada | Transcrição STT | Exact match | STT (s) | Áudio (s) |")
    lines.append("|---|---|---|---|---|---:|---:|")
    for row in results:
        exact_label = "ok" if row["exact_match"] else "falhou"
        lines.append(
            f"| {row['id']} | {row['categoria']} | {row['frase_esperada']} | {row['transcricao_stt']} | {exact_label} | {fmt(float(row['stt_latency_s']))} | {fmt(float(row['audio_duration_s']))} |"
        )
    lines.append(SECTION_END)
    lines.append("")
    return "\n".join(lines)


def inject_stt_section(report_path: Path, stt_section: str) -> None:
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
    else:
        report_text = "# Relatório de Métricas\n\n"

    pattern = re.compile(
        rf"{re.escape(SECTION_START)}.*?{re.escape(SECTION_END)}\n?",
        flags=re.DOTALL,
    )

    if pattern.search(report_text):
        updated = pattern.sub(stt_section, report_text)
    else:
        if report_text.startswith("# "):
            parts = report_text.split("\n", 2)
            if len(parts) >= 2:
                head = "\n".join(parts[:2]).rstrip() + "\n\n"
                tail = parts[2] if len(parts) > 2 else ""
                updated = head + stt_section + tail
            else:
                updated = report_text + "\n" + stt_section
        else:
            updated = stt_section + "\n" + report_text

    report_path.write_text(updated, encoding="utf-8")


def main() -> int:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    report_path = Path(args.report).resolve()
    results_path = Path(args.results_csv).resolve()

    manifest_rows = load_manifest(dataset_dir / "manifest.csv")
    config = load_config()
    stt_cfg = config.get("stt", {})

    stt = FasterWhisperSTT(
        model_size=stt_cfg.get("model", "small"),
        compute_type=stt_cfg.get("compute_type", "int8"),
        language=stt_cfg.get("language"),
        beam_size=stt_cfg.get("beam_size", 5),
        condition_on_previous_text=stt_cfg.get("condition_on_previous_text", True),
    )

    results: list[dict[str, object]] = []
    for row in manifest_rows:
        audio_path = dataset_dir / row["arquivo_audio"]
        audio = load_wav_float32(audio_path)

        t0 = time.perf_counter()
        transcription = stt.transcribe(audio)
        stt_latency_s = time.perf_counter() - t0

        results.append(
            {
                "id": row["id"],
                "categoria": row["categoria"],
                "frase_esperada": row["frase"],
                "transcricao_stt": transcription,
                "exact_match": exact_match(row["frase"], transcription),
                "stt_latency_s": stt_latency_s,
                "audio_duration_s": len(audio) / float(row["sample_rate"]),
                "audio_path": str(audio_path),
            }
        )

    write_results_csv(results_path, results)
    stt_section = build_stt_section(
        results=results,
        stt_model=stt_cfg.get("model", "small"),
        compute_type=stt_cfg.get("compute_type", "int8"),
    )
    inject_stt_section(report_path, stt_section)

    print(report_path)
    print(results_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
