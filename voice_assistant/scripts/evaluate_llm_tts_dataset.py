#!/usr/bin/env python3
"""Evaluate LLM response generation and TTS latency on dataset_teste."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
import statistics
import sys
import time
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import src.llm.openrouter_client as openrouter_client_module
from src.llm.openrouter_client import OpenRouterClient
from src.tts.piper_tts import PiperTTS
from src.utils.config_loader import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate LLM + TTS metrics over dataset_teste.")
    parser.add_argument(
        "--dataset-dir",
        default=str(PROJECT_ROOT / "dataset_teste"),
        help="Dataset directory containing manifest.csv.",
    )
    parser.add_argument(
        "--report",
        default=str(PROJECT_ROOT / "dataset_teste" / "relatorio_metricas_llm_tts.md"),
        help="Output Markdown report path.",
    )
    parser.add_argument(
        "--results-csv",
        default=str(PROJECT_ROOT / "dataset_teste" / "resultados_metricas_llm_tts.csv"),
        help="Output CSV with per-sample results.",
    )
    return parser.parse_args()


def load_manifest(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


_TOOL_STUB_RESPONSES = {
    "bateria": "Bateria em 75%, e sem carregamento.",
    "acender_led": "LED do peito aceso em azul.",
    "apagar_led": "LED do peito apagado.",
    "acender_olhos": "Olhos acesos em azul.",
    "apagar_olhos": "Olhos apagados.",
    "mover_cabeca_esquerda": "Cabeça movida para a esquerda.",
    "mover_cabeca_direita": "Cabeça movida para a direita.",
    "centralizar_cabeca": "Cabeça centralizada.",
}


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


def conversation_id_for_row(row: dict[str, str]) -> str:
    explicit_group = row.get("grupo_conversa", "").strip()
    if explicit_group:
        return explicit_group

    row_id = row["id"]
    if row_id in {"013", "014", "015", "016"}:
        return "dataset-memoria"
    if row_id in {"017", "018", "019", "020"}:
        return "dataset-contexto-acao"
    if row_id in {"021", "022"}:
        return "dataset-memoria-factual"
    if row_id in {"024", "025"}:
        return "dataset-numero"
    return f"dataset-{row_id}"


def keyword_expectation(row: dict[str, str]) -> str | None:
    explicit_keyword = row.get("keyword_esperada", "").strip()
    if explicit_keyword:
        return explicit_keyword

    row_id = row["id"]
    keyword_map = {
        "003": "levant",
        "004": "sent",
        "005": "observ",
        "008": "quatro",
        "014": "danilo",
        "016": "azul",
        "017": "levant",
        "018": "levant",
        "019": "sent",
        "020": "sent",
        "022": "laborat",
        "025": "quarenta e dois",
        "026": "observ",
        "027": "sent",
        "028": "levant",
    }
    return keyword_map.get(row_id)


def keyword_match(response: str, expected_keyword: str | None) -> bool | None:
    if expected_keyword is None:
        return None

    normalized = response.casefold()
    if "|" in expected_keyword:
        return all(part.strip().casefold() in normalized for part in expected_keyword.split("|") if part.strip())
    if expected_keyword == "quarenta e dois":
        return "quarenta e dois" in normalized or "42" in normalized
    return expected_keyword in normalized


def expected_tools(row: dict[str, str]) -> list[str]:
    raw = row.get("tools_esperadas", "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split("|") if part.strip()]


def tool_call_match(expected: list[str], actual: list[str]) -> bool:
    return expected == actual


def build_tracking_registry(called_tools: list[str]) -> dict[str, Callable[[], str]]:
    registry: dict[str, Callable[[], str]] = {}

    for tool_name, response_text in _TOOL_STUB_RESPONSES.items():
        def _tool(name: str = tool_name, response: str = response_text) -> str:
            called_tools.append(name)
            return response

        registry[tool_name] = _tool

    return registry


def write_results_csv(results_path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "categoria",
        "conversation_id",
        "frase",
        "resposta_esperada",
        "tools_esperadas",
        "tools_chamadas",
        "tool_match",
        "resposta_modelo",
        "keyword_esperada",
        "keyword_match",
        "llm_latency_s",
        "tts_latency_s",
        "total_latency_s",
        "response_chars",
        "response_words",
        "tts_audio_duration_s",
        "tts_rtf",
    ]
    with results_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt(value: float) -> str:
    return f"{value:.3f}"


def build_markdown_report(
    manifest_rows: list[dict[str, str]],
    results: list[dict[str, object]],
    llm_model: str,
    tts_model_path: str,
) -> str:
    llm_values = [float(row["llm_latency_s"]) for row in results]
    tts_values = [float(row["tts_latency_s"]) for row in results]
    total_values = [float(row["total_latency_s"]) for row in results]
    chars_values = [float(row["response_chars"]) for row in results]
    words_values = [float(row["response_words"]) for row in results]
    audio_values = [float(row["tts_audio_duration_s"]) for row in results]
    rtf_values = [float(row["tts_rtf"]) for row in results if float(row["tts_audio_duration_s"]) > 0]

    llm_summary = summarize(llm_values)
    tts_summary = summarize(tts_values)
    total_summary = summarize(total_values)
    audio_summary = summarize(audio_values)
    rtf_summary = summarize(rtf_values)

    verifiable_rows = [row for row in results if row["keyword_match"] is not None]
    keyword_hits = sum(1 for row in verifiable_rows if row["keyword_match"] is True)
    keyword_total = len(verifiable_rows)
    keyword_rate = (keyword_hits / keyword_total * 100.0) if keyword_total else 0.0
    tool_hits = sum(1 for row in results if row["tool_match"] is True)
    tool_total = len(results)
    tool_rate = (tool_hits / tool_total * 100.0) if tool_total else 0.0

    lines: list[str] = []
    lines.append("# Relatório de Métricas - LLM e TTS")
    lines.append("")
    lines.append(f"- Gerado em: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- Total de amostras avaliadas: `{len(manifest_rows)}`")
    lines.append(f"- Modelo LLM: `{llm_model}`")
    lines.append(f"- Modelo TTS: `{tts_model_path}`")
    lines.append("")
    lines.append("## Resumo")
    lines.append("")
    lines.append("| Métrica | Média | Mediana | P95 | Mín | Máx |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    lines.append(
        f"| LLM latency (s) | {fmt(llm_summary['mean'])} | {fmt(llm_summary['median'])} | {fmt(llm_summary['p95'])} | {fmt(llm_summary['min'])} | {fmt(llm_summary['max'])} |"
    )
    lines.append(
        f"| TTS latency (s) | {fmt(tts_summary['mean'])} | {fmt(tts_summary['median'])} | {fmt(tts_summary['p95'])} | {fmt(tts_summary['min'])} | {fmt(tts_summary['max'])} |"
    )
    lines.append(
        f"| Total LLM+TTS (s) | {fmt(total_summary['mean'])} | {fmt(total_summary['median'])} | {fmt(total_summary['p95'])} | {fmt(total_summary['min'])} | {fmt(total_summary['max'])} |"
    )
    lines.append(
        f"| Duração do áudio TTS (s) | {fmt(audio_summary['mean'])} | {fmt(audio_summary['median'])} | {fmt(audio_summary['p95'])} | {fmt(audio_summary['min'])} | {fmt(audio_summary['max'])} |"
    )
    lines.append(
        f"| TTS RTF | {fmt(rtf_summary['mean'])} | {fmt(rtf_summary['median'])} | {fmt(rtf_summary['p95'])} | {fmt(rtf_summary['min'])} | {fmt(rtf_summary['max'])} |"
    )
    lines.append("")
    lines.append(f"- Média de caracteres por resposta: `{statistics.mean(chars_values):.1f}`")
    lines.append(f"- Média de palavras por resposta: `{statistics.mean(words_values):.1f}`")
    lines.append(f"- Acurácia de tool calling: `{tool_hits}/{tool_total}` (`{tool_rate:.1f}%`)")
    lines.append(f"- Acurácia heurística por palavra-chave: `{keyword_hits}/{keyword_total}` (`{keyword_rate:.1f}%`)")
    lines.append("")
    lines.append("## Critério heurístico")
    lines.append("")
    lines.append("A coluna `keyword_match` abaixo só é calculada para amostras cuja resposta esperada tem um alvo textual verificável, como `bateria`, `azul`, `esquerda`, `direita` ou `central`. Para os demais casos, ela fica como `n/a`.")
    lines.append("")
    lines.append("## Resultados por amostra")
    lines.append("")
    lines.append("| ID | Categoria | Frase | Tools esperadas | Tools chamadas | tool_match | Esperado | Resposta do modelo | keyword_match | LLM (s) | TTS (s) | Total (s) | Áudio TTS (s) | RTF |")
    lines.append("|---|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|")
    for row in results:
        keyword_value = row["keyword_match"]
        if keyword_value is None:
            keyword_label = "n/a"
        else:
            keyword_label = "ok" if keyword_value else "falhou"
        tool_label = "ok" if row["tool_match"] else "falhou"
        lines.append(
            f"| {row['id']} | {row['categoria']} | {row['frase']} | {row['tools_esperadas']} | {row['tools_chamadas']} | {tool_label} | {row['resposta_esperada']} | {row['resposta_modelo']} | {keyword_label} | {fmt(float(row['llm_latency_s']))} | {fmt(float(row['tts_latency_s']))} | {fmt(float(row['total_latency_s']))} | {fmt(float(row['tts_audio_duration_s']))} | {fmt(float(row['tts_rtf']))} |"
        )
    lines.append("")
    lines.append("## Observações")
    lines.append("")
    lines.append("- Para medir tool calling, as tools foram substituídas por stubs locais que apenas registram a chamada e retornam um texto sintético.")
    lines.append("- As amostras de contexto foram avaliadas em sessões compartilhadas por bloco semântico para preservar memória conversacional.")
    lines.append("- As métricas de geração cobrem latência e um cheque heurístico simples de conteúdo, não uma avaliação semântica completa.")
    lines.append("- O TTS foi medido com `synthesize_raw`, sem playback, então a latência aqui representa síntese e não reprodução no alto-falante.")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    report_path = Path(args.report).resolve()
    results_path = Path(args.results_csv).resolve()

    manifest_rows = load_manifest(dataset_dir / "manifest.csv")
    config = load_config()
    llm_cfg = config.get("llm", {})
    tts_cfg = config.get("tts", {})
    api_keys = config.get("api_keys", {})

    llm = OpenRouterClient(
        model=llm_cfg.get("model", "openai/gpt-4o-mini"),
        api_key=api_keys.get("openrouter"),
        base_url=llm_cfg.get("base_url", "https://openrouter.ai/api/v1/chat/completions"),
        timeout=llm_cfg.get("timeout", 15),
        max_tokens=llm_cfg.get("max_tokens"),
        temperature=llm_cfg.get("temperature"),
        system_prompt=llm_cfg.get("system_prompt", ""),
    )
    tts = PiperTTS(
        model_path=tts_cfg.get("model_path", "models/pt_BR-faber-medium.onnx"),
        sample_rate=tts_cfg.get("sample_rate", 22050),
        espeak_data=tts_cfg.get("espeak_data", "/usr/lib/x86_64-linux-gnu/espeak-ng-data"),
        piper_libs=tts_cfg.get("piper_libs", "/tmp/piper"),
    )

    results: list[dict[str, object]] = []
    original_registry = openrouter_client_module.TOOL_REGISTRY
    try:
        for row in manifest_rows:
            conversation_id = conversation_id_for_row(row)
            called_tools: list[str] = []
            openrouter_client_module.TOOL_REGISTRY = build_tracking_registry(called_tools)

            t0 = time.perf_counter()
            response_text = llm.generate(row["frase"], conversation_id=conversation_id)
            llm_latency_s = time.perf_counter() - t0

            t1 = time.perf_counter()
            raw_pcm = tts.synthesize_raw(response_text)
            tts_latency_s = time.perf_counter() - t1

            tts_audio_duration_s = len(raw_pcm) / 2 / tts.sample_rate if raw_pcm else 0.0
            tts_rtf = (tts_latency_s / tts_audio_duration_s) if tts_audio_duration_s > 0 else 0.0
            expected_keyword = keyword_expectation(row)
            expected_tool_names = expected_tools(row)

            results.append(
                {
                    "id": row["id"],
                    "categoria": row["categoria"],
                    "conversation_id": conversation_id,
                    "frase": row["frase"],
                    "resposta_esperada": row["resposta_esperada"],
                    "tools_esperadas": "|".join(expected_tool_names),
                    "tools_chamadas": "|".join(called_tools),
                    "tool_match": tool_call_match(expected_tool_names, called_tools),
                    "resposta_modelo": response_text,
                    "keyword_esperada": expected_keyword or "",
                    "keyword_match": keyword_match(response_text, expected_keyword),
                    "llm_latency_s": llm_latency_s,
                    "tts_latency_s": tts_latency_s,
                    "total_latency_s": llm_latency_s + tts_latency_s,
                    "response_chars": len(response_text),
                    "response_words": len(response_text.split()),
                    "tts_audio_duration_s": tts_audio_duration_s,
                    "tts_rtf": tts_rtf,
                }
            )
    finally:
        openrouter_client_module.TOOL_REGISTRY = original_registry

    write_results_csv(results_path, results)
    report = build_markdown_report(
        manifest_rows=manifest_rows,
        results=results,
        llm_model=llm.model,
        tts_model_path=tts.model_path,
    )
    report_path.write_text(report, encoding="utf-8")

    print(report_path)
    print(results_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
