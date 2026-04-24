"""Entry point for the Voice Assistant.

Modes
-----
local       (default) – fully local pipeline: mic → STT → LLM → TTS → speaker
server                – UDP server: receive audio → STT → LLM → TTS → stream back
                        (Python UDP client)
client                – UDP client: mic → send audio → receive TTS → speaker
tcp-server            – TCP server: receive WAV → STT → LLM → TTS → send WAV back
                        (bash client using arecord + nc + aplay)
tcp-stream-server     – TCP server: receive raw PCM stream → partial STT overlap
                        → LLM → TTS → send WAV back
                        (bash client using arecord + nc + aplay)

Usage examples
--------------
    # Local mode (default)
    python -m src.main

    # UDP server (Python client on the other machine)
    python -m src.main --mode server --host 0.0.0.0 --port 50007

    # Python UDP client
    python -m src.main --mode client --server-host 192.168.1.10 --port 50007

    # TCP server (bash client using scripts/client.sh)
    python -m src.main --mode tcp-server --host 0.0.0.0 --port 50007

    # TCP streaming server (bash client using scripts/client.sh)
    python -m src.main --mode tcp-stream-server --host 0.0.0.0 --port 50007
"""

import argparse

from src.audio.recorder import AudioRecorder
from src.utils.config_loader import load_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Voice Assistant")
    parser.add_argument(
        "--mode",
        choices=["local", "server", "client", "tcp-server", "tcp-stream-server"],
        default="local",
        help="Operation mode (default: local)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="[server] Bind address (overrides config). Default: 0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="[server/client] UDP port (overrides config). Default: 50007",
    )
    parser.add_argument(
        "--server-host",
        default=None,
        dest="server_host",
        help="[client] Server IP address (overrides config).",
    )
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Enable live UDP audio streaming with overlapped STT processing.",
    )
    return parser.parse_args()


def _build_recorder(audio_cfg: dict) -> AudioRecorder:
    return AudioRecorder(
        sample_rate=audio_cfg.get("sample_rate", 16000),
        channels=audio_cfg.get("channels", 1),
        speech_threshold=audio_cfg.get("speech_threshold", 0.02),
        silence_duration=audio_cfg.get("silence_duration", 0.8),
        max_duration=audio_cfg.get("max_duration", 30.0),
    )


def main() -> None:
    """Initialise components based on mode and start the pipeline."""
    args = _parse_args()
    config = load_config()

    audio_cfg = config.get("audio", {})
    net_cfg = config.get("network", {})
    streaming_enabled = args.streaming or net_cfg.get("streaming", False)

    if args.mode == "client":
        from src.network.udp_client import UDPClient

        server_host = args.server_host or net_cfg.get("server_host", "127.0.0.1")
        port = args.port or net_cfg.get("port", 50007)

        recorder = _build_recorder(audio_cfg)
        client = UDPClient(
            recorder=recorder,
            server_host=server_host,
            server_port=port,
            streaming_enabled=streaming_enabled,
        )
        client.run()
        return

    from src.llm.openrouter_client import OpenRouterClient
    from src.stt.faster_whisper_stt import FasterWhisperSTT
    from src.tts.piper_tts import PiperTTS
    from src.utils.metrics import MetricsLogger

    stt_cfg = config.get("stt", {})
    llm_cfg = config.get("llm", {})
    tts_cfg = config.get("tts", {})
    api_keys = config.get("api_keys", {})

    stt = FasterWhisperSTT(
        model_size=stt_cfg.get("model", "small"),
        compute_type=stt_cfg.get("compute_type", "int8"),
        language=stt_cfg.get("language"),
        beam_size=stt_cfg.get("beam_size", 5),
        condition_on_previous_text=stt_cfg.get("condition_on_previous_text", True),
    )

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

    if args.mode == "server":
        from src.network.udp_server import UDPServer

        host = args.host or net_cfg.get("host", "0.0.0.0")
        port = args.port or net_cfg.get("port", 50007)

        server = UDPServer(
            stt=stt,
            llm=llm,
            tts=tts,
            host=host,
            port=port,
            audio_sample_rate=audio_cfg.get("sample_rate", 16000),
            metrics_logger=MetricsLogger(),
            streaming_enabled=streaming_enabled,
            streaming_min_chunk_s=net_cfg.get("streaming_min_chunk_s", 0.6),
            streaming_update_s=net_cfg.get("streaming_update_s", 0.3),
        )
        server.run()
    elif args.mode == "tcp-server":
        from src.network.tcp_server import TCPServer

        host = args.host or net_cfg.get("host", "0.0.0.0")
        port = args.port or net_cfg.get("tcp_port", net_cfg.get("port", 50007))

        server = TCPServer(
            stt=stt,
            llm=llm,
            tts=tts,
            host=host,
            port=port,
            metrics_logger=MetricsLogger(),
            input_format="wav",
            audio_sample_rate=audio_cfg.get("sample_rate", 16000),
        )
        server.run()
    elif args.mode == "tcp-stream-server":
        from src.network.tcp_server import TCPServer

        host = args.host or net_cfg.get("host", "0.0.0.0")
        port = args.port or net_cfg.get("tcp_port", net_cfg.get("port", 50007))

        server = TCPServer(
            stt=stt,
            llm=llm,
            tts=tts,
            host=host,
            port=port,
            metrics_logger=MetricsLogger(),
            input_format="pcm_s16le",
            audio_sample_rate=audio_cfg.get("sample_rate", 16000),
            streaming_enabled=net_cfg.get("tcp_streaming", True),
            streaming_min_chunk_s=net_cfg.get("tcp_streaming_min_chunk_s", 0.3),
            streaming_update_s=net_cfg.get("tcp_streaming_update_s", 0.15),
        )
        server.run()
    else:
        from src.pipeline.assistant_pipeline import AssistantPipeline

        recorder = _build_recorder(audio_cfg)
        pipeline = AssistantPipeline(
            recorder=recorder,
            stt=stt,
            llm=llm,
            tts=tts,
            metrics_logger=MetricsLogger(),
        )
        pipeline.run()


if __name__ == "__main__":
    main()
