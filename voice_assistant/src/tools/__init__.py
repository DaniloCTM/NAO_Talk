"""Tool registry for assistant actions."""

from src.tools.actions import (
    acender_led,
    acender_olhos,
    apagar_led,
    apagar_olhos,
    bateria,
    centralizar_cabeca,
    mover_cabeca_direita,
    mover_cabeca_esquerda,
)
from src.tools.registry import TOOL_DEFINITIONS, TOOL_REGISTRY

__all__ = [
    "TOOL_DEFINITIONS",
    "TOOL_REGISTRY",
    "bateria",
    "acender_led",
    "apagar_led",
    "acender_olhos",
    "apagar_olhos",
    "mover_cabeca_esquerda",
    "mover_cabeca_direita",
    "centralizar_cabeca",
]
