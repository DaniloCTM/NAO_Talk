"""Assistant actions executed via tool calling."""

from __future__ import annotations

import os
import re
import shutil
import subprocess

from src.utils.logger import get_logger

_DEFAULT_BATTERY_TOPIC = "/sensors/battery"
_DEFAULT_BATTERY_TIMEOUT_S = 3.0
_CHEST_LED_TOPIC = "/effectors/chest_led"
_CHEST_LED_MSG_TYPE = "nao_command_msgs/msg/ChestLed"
logger = get_logger(__name__)


def levanta() -> str:
    """Mock action for standing up."""
    print("Mock action executada: levanta()")
    return "Ação levanta executada com sucesso."


def sentar() -> str:
    """Mock action for sitting down."""
    print("Mock action executada: sentar()")
    return "Ação sentar executada com sucesso."


def observar() -> str:
    """Mock action for observing the environment."""
    print("Mock action executada: observar()")
    return "Ação observar executada com sucesso."


def bateria() -> str:
    """Read the NAO battery level from the nao_lola ROS 2 topic."""
    print("Tool executada: bateria()")
    if shutil.which("ros2") is None:
        return "Não consegui consultar a bateria porque o comando ros2 não está disponível."

    topic = os.getenv("NAO_LOLA_BATTERY_TOPIC", _DEFAULT_BATTERY_TOPIC)
    timeout_s = _battery_timeout_seconds()

    try:
        completed = subprocess.run(
            ["ros2", "topic", "echo", "--once", topic],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Timed out querying battery topic '%s'.", topic)
        return "Não consegui consultar a bateria a tempo no tópico do nao_lola."
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        logger.warning("Battery query failed for topic '%s': %s", topic, details or "no details")
        if details:
            return f"Não consegui consultar a bateria do NAO: {details}"
        return "Não consegui consultar a bateria do NAO."

    parsed = _parse_battery_message(completed.stdout)
    if parsed is None:
        logger.warning("Could not parse battery payload from local ros2 query: %r", completed.stdout)
        return "Recebi dados da bateria, mas não consegui interpretá-los."

    return _format_battery_status(parsed)


def acender_led() -> str:
    """Turn the NAO chest LED blue."""
    print("Tool executada: acender_led()")
    return _set_chest_led(0.0, 0.0, 1.0, success_message="LED do peito aceso em azul.")


def apagar_led() -> str:
    """Turn off the NAO chest LED."""
    print("Tool executada: apagar_led()")
    return _set_chest_led(0.0, 0.0, 0.0, success_message="LED do peito apagado.")


def _format_battery_status(parsed: dict[str, float | bool]) -> str:
    charge = float(parsed["charge"])
    charging = bool(parsed["charging"])
    current = parsed.get("current")
    temperature = parsed.get("temperature")

    parts = [f"Bateria em {charge:.0f}%"]
    parts.append("e carregando" if charging else "e sem carregamento")

    if current is not None:
        parts.append(f"corrente de {float(current):.2f} ampères")
    if temperature is not None:
        parts.append(f"temperatura de {float(temperature):.1f} graus")

    return ", ".join(parts) + "."


def _battery_timeout_seconds() -> float:
    raw_timeout = os.getenv("NAO_LOLA_TOPIC_TIMEOUT", str(_DEFAULT_BATTERY_TIMEOUT_S))
    try:
        return max(0.1, float(raw_timeout))
    except ValueError:
        return _DEFAULT_BATTERY_TIMEOUT_S


def _set_chest_led(red: float, green: float, blue: float, success_message: str) -> str:
    if shutil.which("ros2") is None:
        return "Não consegui controlar o LED porque o comando ros2 não está disponível."

    payload = f"{{ color: {{r: {red:.1f}, g: {green:.1f}, b: {blue:.1f}}}}}"

    try:
        subprocess.run(
            ["ros2", "topic", "pub", "--once", _CHEST_LED_TOPIC, _CHEST_LED_MSG_TYPE, payload],
            check=True,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Timed out publishing chest LED command to '%s'.", _CHEST_LED_TOPIC)
        return "Não consegui controlar o LED a tempo."
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        logger.warning("Chest LED command failed: %s", details or "no details")
        if details:
            return f"Não consegui controlar o LED do NAO: {details}"
        return "Não consegui controlar o LED do NAO."

    return success_message


def _parse_battery_message(payload: str) -> dict[str, float | bool] | None:
    charge = _extract_float(payload, "charge")
    charging = _extract_bool(payload, "charging")
    if charge is None or charging is None:
        return None

    return {
        "charge": charge,
        "charging": charging,
        "current": _extract_float(payload, "current"),
        "temperature": _extract_float(payload, "temperature"),
    }


def _extract_float(payload: str, field: str) -> float | None:
    match = re.search(rf"^{field}:\s*([-+]?\d+(?:\.\d+)?)\s*$", payload, re.MULTILINE)
    if match is None:
        return None
    return float(match.group(1))


def _extract_bool(payload: str, field: str) -> bool | None:
    match = re.search(rf"^{field}:\s*(true|false)\s*$", payload, re.MULTILINE | re.IGNORECASE)
    if match is None:
        return None
    return match.group(1).lower() == "true"
