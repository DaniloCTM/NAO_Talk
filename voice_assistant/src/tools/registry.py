"""Tool definitions exposed to the LLM."""

from src.tools.actions import observar, sentar, levanta

TOOL_REGISTRY = {
    "levanta": levanta,
    "sentar": sentar,
    "observar": observar,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "levanta",
            "description": "Faz o robô levantar. Use quando o usuário pedir para levantar.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sentar",
            "description": "Faz o robô sentar. Use quando o usuário pedir para sentar.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "observar",
            "description": "Faz o robô observar o ambiente. Use quando o usuário pedir para observar ou olhar ao redor.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
]
