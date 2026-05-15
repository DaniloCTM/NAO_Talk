"""LLM client that sends requests to the OpenRouter API."""

from collections import defaultdict, deque
import json
import os

import requests

from src.llm.base_llm import BaseLLM
from src.tools import TOOL_DEFINITIONS, TOOL_REGISTRY
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_MODEL = "openai/gpt-4o-mini"
_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_CONTEXT_TURNS = 6
_DEFAULT_CONVERSATION_ID = "__default__"
_DEFAULT_SYSTEM_PROMPT = (
    "Você é um assistente de voz chamado NAO. "
    "Responda sempre em português, de forma curta e direta, em no máximo duas frases. "
    "Nunca use emojis, markdown, listas ou formatação especial. "
    "Quando o usuário pedir para levantar, sentar ou observar, use a tool correspondente em vez de apenas descrever a ação. "
    "Após executar uma tool, responda com uma confirmação curta adequada para fala."
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
        context_turns: int = _DEFAULT_CONTEXT_TURNS,
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
            context_turns: Number of complete turns retained per conversation.
        """
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_prompt = system_prompt
        self.context_turns = max(1, context_turns)
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self._history: dict[str, deque[list[dict]]] = defaultdict(
            lambda: deque(maxlen=self.context_turns)
        )
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
        )

        if not self._api_key:
            logger.warning("OPENROUTER_API_KEY is not set.")

    def generate(self, prompt: str, conversation_id: str | None = None) -> str:
        """Send a prompt to OpenRouter and return the generated response.

        Args:
            prompt: User input text.
            conversation_id: Optional session identifier for conversation memory.

        Returns:
            Generated response string.

        Raises:
            requests.HTTPError: If the API returns an error status code.
        """
        conversation_key = self._conversation_key(conversation_id)
        messages = self._build_messages(conversation_key)
        current_user_message = {"role": "user", "content": prompt}
        messages.append(current_user_message)

        first_message = self._request_message(messages)
        tool_calls = first_message.get("tool_calls") or []

        if not tool_calls:
            text = self._extract_text(first_message) or "Desculpe, não consegui gerar uma resposta agora."
            self._append_turn(
                conversation_key,
                [
                    current_user_message,
                    {"role": "assistant", "content": text},
                ],
            )
            logger.info("LLM response received (%d chars).", len(text))
            return text

        assistant_tool_message = {
            "role": "assistant",
            "content": first_message.get("content") or "",
            "tool_calls": tool_calls,
        }
        messages.append(assistant_tool_message)

        tool_result_messages = []
        for tool_call in tool_calls:
            tool_response = self._execute_tool_call(tool_call)
            if tool_response is None:
                return "Desculpe, não consegui executar a ação solicitada."

            tool_result_message = {
                "role": "tool",
                "tool_call_id": tool_call.get("id", ""),
                "name": tool_call.get("function", {}).get("name", ""),
                "content": tool_response,
            }
            tool_result_messages.append(tool_result_message)
            messages.append(tool_result_message)

        final_message = self._request_message(messages)
        text = self._extract_text(final_message) or "Pronto."
        self._append_turn(
            conversation_key,
            [
                current_user_message,
                assistant_tool_message,
                *tool_result_messages,
                {"role": "assistant", "content": text},
            ],
        )
        logger.info("LLM response received after tool call (%d chars).", len(text))
        return text

    def _build_messages(self, conversation_key: str) -> list[dict]:
        """Build the message list including system prompt and stored history."""
        messages: list[dict] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        for turn in self._history[conversation_key]:
            messages.extend(turn)
        return messages

    def _append_turn(self, conversation_key: str, turn_messages: list[dict]) -> None:
        """Append a full conversation turn to the in-memory history."""
        self._history[conversation_key].append(list(turn_messages))

    @staticmethod
    def _conversation_key(conversation_id: str | None) -> str:
        """Normalize the conversation identifier used for in-memory history."""
        if conversation_id is None:
            return _DEFAULT_CONVERSATION_ID
        return str(conversation_id)

    def _request_message(self, messages: list[dict]) -> dict:
        """Send a chat completion request and return the assistant message."""
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": TOOL_DEFINITIONS,
            "tool_choice": "auto",
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
        return data["choices"][0]["message"]

    def _execute_tool_call(self, tool_call: dict) -> str | None:
        """Execute a single tool call and return its textual result."""
        function_data = tool_call.get("function", {})
        tool_name = function_data.get("name", "")
        raw_arguments = function_data.get("arguments", "")

        if not self._arguments_are_empty(raw_arguments):
            logger.error("Tool '%s' received unsupported arguments: %s", tool_name, raw_arguments)
            return None

        tool = TOOL_REGISTRY.get(tool_name)
        if tool is None:
            logger.error("Unknown tool requested by the model: %s", tool_name)
            return None

        logger.info("Executing tool '%s'.", tool_name)
        return tool()

    @staticmethod
    def _arguments_are_empty(raw_arguments: str | dict | None) -> bool:
        """Validate that a no-args tool call did not include parameters."""
        if raw_arguments in ("", None):
            return True

        if isinstance(raw_arguments, dict):
            return raw_arguments == {}

        try:
            parsed_arguments = json.loads(raw_arguments)
        except (TypeError, json.JSONDecodeError):
            return False

        return parsed_arguments == {}

    @staticmethod
    def _extract_text(message: dict) -> str:
        """Extract a text response from an assistant message."""
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        return ""
