"""Pipeline controller that orchestrates the full voice assistant flow."""

from src.audio.recorder import AudioRecorder
from src.llm.base_llm import BaseLLM
from src.stt.base_stt import BaseSTT
from src.tts.base_tts import BaseTTS
from src.utils.logger import get_logger
from src.utils.metrics import MetricsLogger, timer

logger = get_logger(__name__)


class AssistantPipeline:
    """Orchestrates the record → STT → LLM → TTS loop."""

    def __init__(
        self,
        recorder: AudioRecorder,
        stt: BaseSTT,
        llm: BaseLLM,
        tts: BaseTTS,
        metrics_logger: MetricsLogger | None = None,
    ):
        """Initialise the pipeline with its components.

        Args:
            recorder: Audio capture component.
            stt: Speech-to-text component.
            llm: Language model component.
            tts: Text-to-speech component.
            metrics_logger: Optional metrics logger. If None, no CSV is written.
        """
        self.recorder = recorder
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.metrics_logger = metrics_logger

    def run_once(self) -> bool:
        """Execute a single record → STT → LLM → TTS cycle.

        Returns:
            True if a full cycle completed, False if no speech was detected.
        """
        metrics = self.metrics_logger.next_turn() if self.metrics_logger else None

        with timer() as t_audio:
            audio = self.recorder.record()
        if metrics:
            metrics.audio_duration_s = len(audio) / self.recorder.sample_rate

        with timer() as t_stt:
            text = self.stt.transcribe(audio)
        if metrics:
            metrics.stt_latency_s = t_stt[0]
            metrics.transcription = text

        if not text:
            logger.info("No speech detected, skipping.")
            return False

        logger.info("User said: %s", text)

        with timer() as t_llm:
            try:
                response = self.llm.generate(text, conversation_id=None)
            except Exception as exc:
                logger.exception("LLM generation failed: %s", exc)
                response = "Desculpe, ocorreu um erro ao processar sua solicitação."
        if metrics:
            metrics.llm_latency_s = t_llm[0]
            metrics.response_chars = len(response)

        logger.info("Assistant: %s", response)

        with timer() as t_tts:
            self.tts.speak(response)
        if metrics:
            metrics.tts_latency_s = t_tts[0]
            self.metrics_logger.log(metrics)

        return True

    def run(self) -> None:
        """Run the pipeline in an infinite loop until interrupted."""
        logger.info("Voice assistant started. Press Ctrl+C to stop.")
        try:
            while True:
                self.run_once()
        except KeyboardInterrupt:
            logger.info("Voice assistant stopped.")
