#!/usr/bin/env python3
"""Record labeled audio samples for the voice assistant test dataset."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import wave

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.audio.recorder import AudioRecorder
from src.utils.config_loader import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record labeled audio for dataset_teste.")
    parser.add_argument(
        "--dataset-dir",
        default=str(PROJECT_ROOT / "dataset_teste"),
        help="Target dataset directory. Default: voice_assistant/dataset_teste",
    )
    parser.add_argument(
        "--prompts-file",
        default=str(PROJECT_ROOT / "dataset_teste" / "prompts_default.json"),
        help="JSON file containing the prompts and expected responses.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        help="Override the sample rate from config.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Input device name or index for sounddevice.",
    )
    parser.add_argument(
        "--start-at",
        default=None,
        help="Start recording from a specific prompt id.",
    )
    return parser.parse_args()


def load_prompts(prompts_path: Path) -> list[dict]:
    with prompts_path.open("r", encoding="utf-8") as file:
        prompts = json.load(file)

    if not isinstance(prompts, list):
        raise ValueError("Prompt file must contain a list of entries.")

    required_fields = {"id", "categoria", "frase", "resposta_esperada"}
    for item in prompts:
        missing = required_fields - set(item)
        if missing:
            raise ValueError(f"Prompt entry missing fields: {sorted(missing)}")

    return prompts


def ensure_dataset_layout(dataset_dir: Path) -> tuple[Path, Path, Path]:
    audio_dir = dataset_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    manifest_csv = dataset_dir / "manifest.csv"
    manifest_jsonl = dataset_dir / "manifest.jsonl"
    return audio_dir, manifest_csv, manifest_jsonl


def write_wav(audio_path: Path, audio: np.ndarray, sample_rate: int) -> None:
    pcm = np.clip(audio * 32768.0, -32768, 32767).astype(np.int16)
    with wave.open(str(audio_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())


def load_existing_rows(manifest_csv: Path) -> list[dict]:
    if not manifest_csv.exists():
        return []

    with manifest_csv.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_manifests(manifest_csv: Path, manifest_jsonl: Path, rows: list[dict]) -> None:
    fieldnames = [
        "id",
        "categoria",
        "frase",
        "resposta_esperada",
        "arquivo_audio",
        "sample_rate",
        "duracao_s",
    ]
    with manifest_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with manifest_jsonl.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def sanitize_label(value: str) -> str:
    sanitized = "".join(char if char.isalnum() else "_" for char in value.lower())
    return "_".join(part for part in sanitized.split("_") if part)


def should_start(item_id: str, start_at: str | None, started: bool) -> bool:
    if started or start_at is None:
        return True
    return item_id == start_at


def main() -> int:
    args = parse_args()
    config = load_config()
    audio_cfg = config.get("audio", {})

    dataset_dir = Path(args.dataset_dir).resolve()
    prompts_path = Path(args.prompts_file).resolve()
    prompts = load_prompts(prompts_path)
    audio_dir, manifest_csv, manifest_jsonl = ensure_dataset_layout(dataset_dir)

    recorder = AudioRecorder(
        sample_rate=args.sample_rate or audio_cfg.get("sample_rate", 16000),
        channels=audio_cfg.get("channels", 1),
        device=args.device,
        speech_threshold=audio_cfg.get("speech_threshold", 0.02),
        silence_duration=audio_cfg.get("silence_duration", 0.8),
        max_duration=audio_cfg.get("max_duration", 30.0),
        vad_mode=audio_cfg.get("vad_mode", "webrtc"),
        vad_aggressiveness=audio_cfg.get("vad_aggressiveness", 2),
        vad_frame_ms=audio_cfg.get("vad_frame_ms", 30),
    )

    rows_by_id = {row["id"]: row for row in load_existing_rows(manifest_csv)}
    started = args.start_at is None

    print("=== Gravador de dataset_teste ===")
    print(f"Dataset: {dataset_dir}")
    print(f"Prompts: {prompts_path}")
    print(f"Sample rate: {recorder.sample_rate} Hz | VAD: {recorder.active_vad_mode}")
    print("Controles: Enter = gravar | r = regravar item atual | s = pular | q = sair")
    print("")

    for index, item in enumerate(prompts, start=1):
        item_id = str(item["id"])
        started = should_start(item_id, args.start_at, started)
        if not started:
            continue

        category_tag = sanitize_label(item["categoria"])
        audio_filename = f"{item_id}_{category_tag}.wav"
        audio_path = audio_dir / audio_filename

        while True:
            print(f"[{index:02d}/{len(prompts)}] ID {item_id} | categoria: {item['categoria']}")
            print(f"Frase: {item['frase']}")
            print(f"Resposta esperada: {item['resposta_esperada']}")
            if audio_path.exists():
                print(f"Arquivo atual: {audio_path.name}")

            command = input("Ação [Enter/r/s/q]: ").strip().lower()
            if command == "q":
                ordered_rows = [rows_by_id[key] for key in sorted(rows_by_id)]
                write_manifests(manifest_csv, manifest_jsonl, ordered_rows)
                print("Manifestos salvos. Encerrando.")
                return 0
            if command == "s":
                print("Item pulado.\n")
                break

            print("Fale a frase após o aviso do gravador.")
            audio = recorder.record()
            if audio.size == 0:
                print("Nenhuma fala detectada. Tente novamente.\n")
                continue

            write_wav(audio_path, audio, recorder.sample_rate)
            duration_s = len(audio) / recorder.sample_rate
            rows_by_id[item_id] = {
                "id": item_id,
                "categoria": item["categoria"],
                "frase": item["frase"],
                "resposta_esperada": item["resposta_esperada"],
                "arquivo_audio": str(audio_path.relative_to(dataset_dir)),
                "sample_rate": str(recorder.sample_rate),
                "duracao_s": f"{duration_s:.3f}",
            }
            ordered_rows = [rows_by_id[key] for key in sorted(rows_by_id)]
            write_manifests(manifest_csv, manifest_jsonl, ordered_rows)
            print(f"Gravação salva em {audio_path.name} ({duration_s:.2f}s).\n")

            confirm = input("Aceitar gravação? [Enter=sim / r=regravar / s=pular]: ").strip().lower()
            if confirm == "r":
                audio_path.unlink(missing_ok=True)
                rows_by_id.pop(item_id, None)
                ordered_rows = [rows_by_id[key] for key in sorted(rows_by_id)]
                write_manifests(manifest_csv, manifest_jsonl, ordered_rows)
                print("Gravação removida. Vamos tentar de novo.\n")
                continue
            if confirm == "s":
                audio_path.unlink(missing_ok=True)
                rows_by_id.pop(item_id, None)
                ordered_rows = [rows_by_id[key] for key in sorted(rows_by_id)]
                write_manifests(manifest_csv, manifest_jsonl, ordered_rows)
                print("Gravação descartada e item pulado.\n")
            break

    ordered_rows = [rows_by_id[key] for key in sorted(rows_by_id)]
    write_manifests(manifest_csv, manifest_jsonl, ordered_rows)
    print("Dataset concluído.")
    print(f"Manifest CSV: {manifest_csv}")
    print(f"Manifest JSONL: {manifest_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
