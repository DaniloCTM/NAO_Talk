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
_RIGHT_EYE_LED_TOPIC = "/effectors/right_eye_leds"
_RIGHT_EYE_LED_MSG_TYPE = "nao_command_msgs/msg/RightEyeLeds"
_LEFT_EYE_LED_TOPIC = "/effectors/left_eye_leds"
_LEFT_EYE_LED_MSG_TYPE = "nao_command_msgs/msg/LeftEyeLeds"
_JOINT_STIFFNESSES_TOPIC = "/effectors/joint_stiffnesses"
_JOINT_STIFFNESSES_MSG_TYPE = "nao_command_msgs/msg/JointStiffnesses"
_JOINT_POSITIONS_TOPIC = "/effectors/joint_positions"
_JOINT_POSITIONS_MSG_TYPE = "nao_command_msgs/msg/JointPositions"
_DEFAULT_LED_TIMEOUT_S = 5.0
_DEFAULT_LED_WAIT_SUBSCRIPTIONS = 1
_DEFAULT_MOTION_TIMEOUT_S = 5.0
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


def acender_olhos() -> str:
    """Turn both NAO eye LEDs blue."""
    print("Tool executada: acender_olhos()")
    return _set_eye_leds(0.0, 0.0, 1.0, success_message="Olhos acesos em azul.")


def apagar_olhos() -> str:
    """Turn off both NAO eye LEDs."""
    print("Tool executada: apagar_olhos()")
    return _set_eye_leds(0.0, 0.0, 0.0, success_message="Olhos apagados.")


def mover_cabeca_esquerda() -> str:
    """Move the NAO head slightly to the left."""
    print("Tool executada: mover_cabeca_esquerda()")
    return _move_joint(index=0, stiffness=0.5, position=0.45, success_message="Cabeça movida para a esquerda.")


def mover_cabeca_direita() -> str:
    """Move the NAO head slightly to the right."""
    print("Tool executada: mover_cabeca_direita()")
    return _move_joint(index=0, stiffness=0.5, position=-0.45, success_message="Cabeça movida para a direita.")


def centralizar_cabeca() -> str:
    """Return the NAO head to the center position."""
    print("Tool executada: centralizar_cabeca()")
    return _move_joint(index=0, stiffness=0.5, position=0.0, success_message="Cabeça centralizada.")


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
    wait_subscriptions = os.getenv(
        "NAO_LED_WAIT_MATCHING_SUBSCRIPTIONS",
        str(_DEFAULT_LED_WAIT_SUBSCRIPTIONS),
    )
    timeout_s = _led_timeout_seconds()

    try:
        completed = subprocess.run(
            [
                "ros2",
                "topic",
                "pub",
                "--once",
                "-w",
                wait_subscriptions,
                _CHEST_LED_TOPIC,
                _CHEST_LED_MSG_TYPE,
                payload,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_s,
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

    logger.info("Chest LED command acknowledged: %s", (completed.stdout or completed.stderr or "").strip())
    return success_message


def _led_timeout_seconds() -> float:
    raw_timeout = os.getenv("NAO_LED_TIMEOUT", str(_DEFAULT_LED_TIMEOUT_S))
    try:
        return max(0.1, float(raw_timeout))
    except ValueError:
        return _DEFAULT_LED_TIMEOUT_S


def _set_eye_leds(red: float, green: float, blue: float, success_message: str) -> str:
    if shutil.which("ros2") is None:
        return "Não consegui controlar os olhos porque o comando ros2 não está disponível."

    color_block = ", ".join([f"{{r: {red:.1f}, g: {green:.1f}, b: {blue:.1f}}}"] * 8)
    payload = f"{{ colors: [{color_block}] }}"
    timeout_s = _led_timeout_seconds()

    try:
        _publish_ros2_once(_RIGHT_EYE_LED_TOPIC, _RIGHT_EYE_LED_MSG_TYPE, payload, timeout_s=timeout_s)
        _publish_ros2_once(_LEFT_EYE_LED_TOPIC, _LEFT_EYE_LED_MSG_TYPE, payload, timeout_s=timeout_s)
    except subprocess.TimeoutExpired:
        logger.warning("Timed out publishing eye LED command.")
        return "Não consegui controlar os olhos a tempo."
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        logger.warning("Eye LED command failed: %s", details or "no details")
        if details:
            return f"Não consegui controlar os olhos do NAO: {details}"
        return "Não consegui controlar os olhos do NAO."

    return success_message


def _motion_timeout_seconds() -> float:
    raw_timeout = os.getenv("NAO_MOTION_TIMEOUT", str(_DEFAULT_MOTION_TIMEOUT_S))
    try:
        return max(0.1, float(raw_timeout))
    except ValueError:
        return _DEFAULT_MOTION_TIMEOUT_S


def _move_joint(index: int, stiffness: float, position: float, success_message: str) -> str:
    if shutil.which("ros2") is None:
        return "Não consegui mover a cabeça porque o comando ros2 não está disponível."

    timeout_s = _motion_timeout_seconds()

    try:
        _publish_ros2_once(
            _JOINT_STIFFNESSES_TOPIC,
            _JOINT_STIFFNESSES_MSG_TYPE,
            f"{{indexes: [{index}], stiffnesses: [{stiffness:.1f}]}}",
            timeout_s=timeout_s,
        )
        _publish_ros2_once(
            _JOINT_POSITIONS_TOPIC,
            _JOINT_POSITIONS_MSG_TYPE,
            f"{{indexes: [{index}], positions: [{position:.2f}]}}",
            timeout_s=timeout_s,
        )
        _publish_ros2_once(
            _JOINT_STIFFNESSES_TOPIC,
            _JOINT_STIFFNESSES_MSG_TYPE,
            f"{{indexes: [{index}], stiffnesses: [0.0]}}",
            timeout_s=timeout_s,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Timed out publishing head movement command.")
        return "Não consegui mover a cabeça a tempo."
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip()
        logger.warning("Head movement command failed: %s", details or "no details")
        if details:
            return f"Não consegui mover a cabeça do NAO: {details}"
        return "Não consegui mover a cabeça do NAO."

    return success_message


def _publish_ros2_once(topic: str, msg_type: str, payload: str, timeout_s: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ros2", "topic", "pub", "--once", topic, msg_type, payload],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


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
