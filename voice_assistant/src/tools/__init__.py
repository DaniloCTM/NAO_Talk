"""Tool registry for assistant actions."""

from src.tools.actions import acender_led, apagar_led, bateria, observar, sentar, levanta
from src.tools.registry import TOOL_DEFINITIONS, TOOL_REGISTRY

__all__ = [
    "TOOL_DEFINITIONS",
    "TOOL_REGISTRY",
    "levanta",
    "sentar",
    "observar",
    "bateria",
    "acender_led",
    "apagar_led",
]
