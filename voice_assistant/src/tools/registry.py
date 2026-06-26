"""Tool definitions exposed to the LLM."""

from src.tools.actions import acender_led, apagar_led, bateria, observar, sentar, levanta

TOOL_REGISTRY = {
    "levanta": levanta,
    "sentar": sentar,
    "observar": observar,
    "bateria": bateria,
    "acender_led": acender_led,
    "apagar_led": apagar_led,
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
    {
        "type": "function",
        "function": {
            "name": "bateria",
            "description": "Consulta a bateria do robô NAO via nao_lola. Use quando o usuário perguntar sobre bateria, carga, nível de energia ou se o robô está carregando.",
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
            "name": "acender_led",
            "description": "Acende o LED do peito do robô em azul. Use quando o usuário pedir para acender a luz ou ligar o LED do peito.",
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
            "name": "apagar_led",
            "description": "Apaga o LED do peito do robô. Use quando o usuário pedir para apagar a luz ou desligar o LED do peito.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
]
