"""LLM client that sends requests to the OpenRouter API."""

import os

import requests

from src.llm.base_llm import BaseLLM
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_MODEL = "openai/gpt-4o-mini"
_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_SYSTEM_PROMPT = (
    "Você é um assistente de voz. "
    "Responda sempre em português, de forma curta e direta, em no máximo duas frases. "
    "Nunca use emojis, markdown, listas ou formatação especial."
)


class OpenRouterClient(BaseLLM):
    """LLM backend powered by OpenRouter."""

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = _API_URL,
        timeout: int = 15,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system_prompt: str = _DEFAULT_SYSTEM_PROMPT,
    ):
        """Initialize the OpenRouter client.

        Args:
            model: OpenRouter model identifier.
            api_key: API key. Falls back to OPENROUTER_API_KEY env var.
            base_url: OpenRouter API endpoint URL.
            timeout: HTTP request timeout in seconds.
            max_tokens: Optional cap for generated tokens.
            temperature: Optional sampling temperature.
            system_prompt: System message sent before every user turn.
        """
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_prompt = system_prompt
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        )

        if not self._api_key:
            logger.warning("OPENROUTER_API_KEY is not set.")

    def generate(self, prompt: str) -> str:
        """Send a prompt to OpenRouter and return the generated response.

        Args:
            prompt: User input text.

        Returns:
            Generated response string.

        Raises:
            requests.HTTPError: If the API returns an error status code.
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            payload["temperature"] = self.temperature

        logger.debug("Sending prompt to OpenRouter (model=%s).", self.model)
        response = self._session.post(
            self.base_url,
            json=payload,
            timeout=self.timeout,
        )
        if not response.ok:
            logger.error("OpenRouter error %d: %s", response.status_code, response.text)
            response.raise_for_status()

        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        logger.info("LLM response received (%d chars).", len(text))
        return text
