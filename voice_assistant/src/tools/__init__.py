"""Tool registry for assistant actions."""

from src.tools.actions import observar, sentar, levanta
from src.tools.registry import TOOL_DEFINITIONS, TOOL_REGISTRY

__all__ = [
    "TOOL_DEFINITIONS",
    "TOOL_REGISTRY",
    "levanta",
    "sentar",
    "observar",
]
