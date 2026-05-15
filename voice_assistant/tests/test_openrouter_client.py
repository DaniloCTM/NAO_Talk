from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.openrouter_client import OpenRouterClient


class FakeResponse:
    def __init__(self, payload: dict, ok: bool = True, status_code: int = 200, text: str = ""):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code
        self.text = text

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError(self.text or f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.calls: list[dict] = []
        self.headers = {}

    def update(self, headers: dict) -> None:
        self.headers.update(headers)

    def post(self, url: str, json: dict, timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return self.responses.pop(0)


class OpenRouterClientTest(unittest.TestCase):
    def test_generate_returns_plain_text_without_tool_call(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Tudo certo.",
                                }
                            }
                        ]
                    }
                )
            ]
        )
        client = OpenRouterClient(api_key="test-key")
        client._session = session

        result = client.generate("Oi")

        self.assertEqual(result, "Tudo certo.")
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0]["json"]["tools"][0]["function"]["name"], "levanta")
        self.assertEqual(session.calls[0]["json"]["messages"][-1]["content"], "Oi")

    def test_generate_executes_levanta_tool_and_returns_followup_text(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call-1",
                                            "type": "function",
                                            "function": {"name": "levanta", "arguments": "{}"},
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                ),
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Estou levantando agora.",
                                }
                            }
                        ]
                    }
                ),
            ]
        )
        client = OpenRouterClient(api_key="test-key")
        client._session = session

        with patch("src.llm.openrouter_client.TOOL_REGISTRY", {"levanta": lambda: "Ação levanta executada com sucesso."}):
            result = client.generate("Levante-se")

        self.assertEqual(result, "Estou levantando agora.")
        self.assertEqual(len(session.calls), 2)
        followup_messages = session.calls[1]["json"]["messages"]
        self.assertEqual(followup_messages[-1]["role"], "tool")
        self.assertEqual(followup_messages[-1]["name"], "levanta")
        self.assertEqual(followup_messages[-1]["content"], "Ação levanta executada com sucesso.")

    def test_generate_executes_observar_tool(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call-2",
                                            "type": "function",
                                            "function": {"name": "observar", "arguments": "{}"},
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                ),
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Estou observando o ambiente.",
                                }
                            }
                        ]
                    }
                ),
            ]
        )
        client = OpenRouterClient(api_key="test-key")
        client._session = session

        with patch("src.llm.openrouter_client.TOOL_REGISTRY", {"observar": lambda: "Ação observar executada com sucesso."}):
            result = client.generate("Observe ao redor")

        self.assertEqual(result, "Estou observando o ambiente.")
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[1]["json"]["messages"][-1]["name"], "observar")

    def test_generate_executes_multiple_tool_calls(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call-a",
                                            "type": "function",
                                            "function": {"name": "levanta", "arguments": "{}"},
                                        },
                                        {
                                            "id": "call-b",
                                            "type": "function",
                                            "function": {"name": "observar", "arguments": "{}"},
                                        },
                                    ],
                                }
                            }
                        ]
                    }
                ),
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Levantando e observando agora.",
                                }
                            }
                        ]
                    }
                ),
            ]
        )
        client = OpenRouterClient(api_key="test-key")
        client._session = session

        with patch(
            "src.llm.openrouter_client.TOOL_REGISTRY",
            {
                "levanta": lambda: "Ação levanta executada com sucesso.",
                "observar": lambda: "Ação observar executada com sucesso.",
            },
        ):
            result = client.generate("Levante e observe", conversation_id="sessao-multi")

        self.assertEqual(result, "Levantando e observando agora.")
        followup_messages = session.calls[1]["json"]["messages"]
        self.assertEqual(followup_messages[-2]["role"], "tool")
        self.assertEqual(followup_messages[-2]["name"], "levanta")
        self.assertEqual(followup_messages[-1]["role"], "tool")
        self.assertEqual(followup_messages[-1]["name"], "observar")

    def test_generate_falls_back_when_tool_is_unknown(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call-3",
                                            "type": "function",
                                            "function": {"name": "desconhecida", "arguments": "{}"},
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                )
            ]
        )
        client = OpenRouterClient(api_key="test-key")
        client._session = session

        result = client.generate("Faça algo")

        self.assertEqual(result, "Desculpe, não consegui executar a ação solicitada.")
        self.assertEqual(len(session.calls), 1)

    def test_generate_keeps_history_for_same_conversation(self):
        session = FakeSession(
            [
                FakeResponse({"choices": [{"message": {"content": "Oi também."}}]}),
                FakeResponse({"choices": [{"message": {"content": "Você disse que seu nome é Danilo."}}]}),
            ]
        )
        client = OpenRouterClient(api_key="test-key")
        client._session = session

        first = client.generate("Meu nome é Danilo", conversation_id="sessao-1")
        second = client.generate("Qual é meu nome?", conversation_id="sessao-1")

        self.assertEqual(first, "Oi também.")
        self.assertEqual(second, "Você disse que seu nome é Danilo.")
        self.assertEqual(len(session.calls), 2)
        second_call_messages = session.calls[1]["json"]["messages"]
        self.assertEqual(second_call_messages[1]["role"], "user")
        self.assertEqual(second_call_messages[1]["content"], "Meu nome é Danilo")
        self.assertEqual(second_call_messages[2]["role"], "assistant")
        self.assertEqual(second_call_messages[2]["content"], "Oi também.")
        self.assertEqual(second_call_messages[-1]["content"], "Qual é meu nome?")

    def test_generate_isolates_history_between_conversations(self):
        session = FakeSession(
            [
                FakeResponse({"choices": [{"message": {"content": "Resposta A1"}}]}),
                FakeResponse({"choices": [{"message": {"content": "Resposta B1"}}]}),
                FakeResponse({"choices": [{"message": {"content": "Resposta A2"}}]}),
            ]
        )
        client = OpenRouterClient(api_key="test-key")
        client._session = session

        client.generate("Mensagem A1", conversation_id="sessao-A")
        client.generate("Mensagem B1", conversation_id="sessao-B")
        client.generate("Mensagem A2", conversation_id="sessao-A")

        third_call_messages = session.calls[2]["json"]["messages"]
        contents = [message.get("content", "") for message in third_call_messages]
        self.assertIn("Mensagem A1", contents)
        self.assertIn("Resposta A1", contents)
        self.assertNotIn("Mensagem B1", contents)
        self.assertNotIn("Resposta B1", contents)

    def test_generate_limits_history_to_last_six_turns(self):
        session = FakeSession(
            [FakeResponse({"choices": [{"message": {"content": f"Resposta {idx}"}}]}) for idx in range(8)]
        )
        client = OpenRouterClient(api_key="test-key", context_turns=6)
        client._session = session

        for idx in range(8):
            client.generate(f"Pergunta {idx}", conversation_id="sessao-limitada")

        last_call_messages = session.calls[-1]["json"]["messages"]
        contents = [message.get("content", "") for message in last_call_messages]
        self.assertNotIn("Pergunta 0", contents)
        self.assertNotIn("Resposta 0", contents)
        self.assertIn("Pergunta 1", contents)
        self.assertIn("Resposta 6", contents)
        self.assertIn("Pergunta 7", contents)

    def test_generate_persists_tool_turn_in_history(self):
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call-9",
                                            "type": "function",
                                            "function": {"name": "levanta", "arguments": "{}"},
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                ),
                FakeResponse({"choices": [{"message": {"content": "Estou levantando agora."}}]}),
                FakeResponse({"choices": [{"message": {"content": "Lembro que acabei de levantar."}}]}),
            ]
        )
        client = OpenRouterClient(api_key="test-key")
        client._session = session

        with patch("src.llm.openrouter_client.TOOL_REGISTRY", {"levanta": lambda: "Ação levanta executada com sucesso."}):
            client.generate("Levante-se", conversation_id="sessao-tool")
            result = client.generate("O que você acabou de fazer?", conversation_id="sessao-tool")

        self.assertEqual(result, "Lembro que acabei de levantar.")
        third_call_messages = session.calls[2]["json"]["messages"]
        roles = [message["role"] for message in third_call_messages]
        self.assertEqual(roles[1:5], ["user", "assistant", "tool", "assistant"])
        self.assertEqual(third_call_messages[2]["tool_calls"][0]["function"]["name"], "levanta")
        self.assertEqual(third_call_messages[3]["name"], "levanta")
        self.assertEqual(third_call_messages[4]["content"], "Estou levantando agora.")


if __name__ == "__main__":
    unittest.main()
