"""Tool definitions exposed to the LLM."""

from src.tools.actions import (
    acender_led,
    acender_olhos,
    apagar_led,
    apagar_olhos,
    bateria,
    centralizar_cabeca,
    mover_cabeca_direita,
    mover_cabeca_esquerda,
    observar,
    sentar,
    levanta,
)

TOOL_REGISTRY = {
    "levanta": levanta,
    "sentar": sentar,
    "observar": observar,
    "bateria": bateria,
    "acender_led": acender_led,
    "apagar_led": apagar_led,
    "acender_olhos": acender_olhos,
    "apagar_olhos": apagar_olhos,
    "mover_cabeca_esquerda": mover_cabeca_esquerda,
    "mover_cabeca_direita": mover_cabeca_direita,
    "centralizar_cabeca": centralizar_cabeca,
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
    {
        "type": "function",
        "function": {
            "name": "acender_olhos",
            "description": "Acende os olhos do robô em azul. Use quando o usuário pedir para acender os olhos ou ligar as luzes dos olhos.",
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
            "name": "apagar_olhos",
            "description": "Apaga os olhos do robô. Use quando o usuário pedir para apagar os olhos ou desligar as luzes dos olhos.",
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
            "name": "mover_cabeca_esquerda",
            "description": "Move a cabeça do robô para a esquerda. Use quando o usuário pedir para virar a cabeça para a esquerda ou olhar para a esquerda.",
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
            "name": "mover_cabeca_direita",
            "description": "Move a cabeça do robô para a direita. Use quando o usuário pedir para virar a cabeça para a direita ou olhar para a direita.",
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
            "name": "centralizar_cabeca",
            "description": "Volta a cabeça do robô para o centro. Use quando o usuário pedir para centralizar a cabeça, olhar para frente ou voltar a cabeça para a posição inicial.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
]
