from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


class ToolsTest(unittest.TestCase):
    def test_tool_registry_exposes_expected_tools(self):
        self.assertEqual(
            set(TOOL_REGISTRY),
            {
                "bateria",
                "acender_led",
                "apagar_led",
                "acender_olhos",
                "apagar_olhos",
                "mover_cabeca_esquerda",
                "mover_cabeca_direita",
                "centralizar_cabeca",
            },
        )
        self.assertIs(TOOL_REGISTRY["bateria"], bateria)
        self.assertIs(TOOL_REGISTRY["acender_led"], acender_led)
        self.assertIs(TOOL_REGISTRY["apagar_led"], apagar_led)
        self.assertIs(TOOL_REGISTRY["acender_olhos"], acender_olhos)
        self.assertIs(TOOL_REGISTRY["apagar_olhos"], apagar_olhos)
        self.assertIs(TOOL_REGISTRY["mover_cabeca_esquerda"], mover_cabeca_esquerda)
        self.assertIs(TOOL_REGISTRY["mover_cabeca_direita"], mover_cabeca_direita)
        self.assertIs(TOOL_REGISTRY["centralizar_cabeca"], centralizar_cabeca)

        definition_names = {item["function"]["name"] for item in TOOL_DEFINITIONS}
        self.assertEqual(
            definition_names,
            {
                "bateria",
                "acender_led",
                "apagar_led",
                "acender_olhos",
                "apagar_olhos",
                "mover_cabeca_esquerda",
                "mover_cabeca_direita",
                "centralizar_cabeca",
            },
        )

    def test_bateria_reads_ros2_topic(self):
        ros_output = "\n".join(
            [
                "charge: 87.5",
                "charging: false",
                "current: -0.42",
                "temperature: 31.2",
            ]
        )
        completed = Mock(stdout=ros_output)

        with patch("builtins.print") as mocked_print, patch("src.tools.actions.shutil.which", return_value="/usr/bin/ros2"), patch(
            "src.tools.actions.subprocess.run", return_value=completed
        ) as mocked_run:
            result = bateria()

        mocked_print.assert_called_once_with("Tool executada: bateria()")
        mocked_run.assert_called_once_with(
            ["ros2", "topic", "echo", "--once", "/sensors/battery"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        self.assertEqual(
            result,
            "Bateria em 88%, e sem carregamento, corrente de -0.42 ampères, temperatura de 31.2 graus.",
        )

    def test_bateria_returns_friendly_message_when_ros2_is_missing(self):
        with patch("builtins.print"), patch("src.tools.actions.shutil.which", return_value=None):
            result = bateria()

        self.assertEqual(
            result,
            "Não consegui consultar a bateria porque o comando ros2 não está disponível.",
        )

    def test_acender_led_publishes_blue_command(self):
        completed = Mock()

        with patch("builtins.print") as mocked_print, patch("src.tools.actions.shutil.which", return_value="/usr/bin/ros2"), patch(
            "src.tools.actions.subprocess.run", return_value=completed
        ) as mocked_run:
            result = acender_led()

        mocked_print.assert_called_once_with("Tool executada: acender_led()")
        mocked_run.assert_called_once_with(
            [
                "ros2",
                "topic",
                "pub",
                "--once",
                "-w",
                "1",
                "/effectors/chest_led",
                "nao_command_msgs/msg/ChestLed",
                "{ color: {r: 0.0, g: 0.0, b: 1.0}}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        self.assertEqual(result, "LED do peito aceso em azul.")

    def test_apagar_led_publishes_off_command(self):
        completed = Mock()

        with patch("builtins.print") as mocked_print, patch("src.tools.actions.shutil.which", return_value="/usr/bin/ros2"), patch(
            "src.tools.actions.subprocess.run", return_value=completed
        ) as mocked_run:
            result = apagar_led()

        mocked_print.assert_called_once_with("Tool executada: apagar_led()")
        mocked_run.assert_called_once_with(
            [
                "ros2",
                "topic",
                "pub",
                "--once",
                "-w",
                "1",
                "/effectors/chest_led",
                "nao_command_msgs/msg/ChestLed",
                "{ color: {r: 0.0, g: 0.0, b: 0.0}}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        self.assertEqual(result, "LED do peito apagado.")

    def test_acender_olhos_publishes_both_eye_commands(self):
        completed = Mock()
        payload = "{ colors: [{r: 0.0, g: 0.0, b: 1.0}, {r: 0.0, g: 0.0, b: 1.0}, {r: 0.0, g: 0.0, b: 1.0}, {r: 0.0, g: 0.0, b: 1.0}, {r: 0.0, g: 0.0, b: 1.0}, {r: 0.0, g: 0.0, b: 1.0}, {r: 0.0, g: 0.0, b: 1.0}, {r: 0.0, g: 0.0, b: 1.0}] }"

        with patch("builtins.print") as mocked_print, patch("src.tools.actions.shutil.which", return_value="/usr/bin/ros2"), patch(
            "src.tools.actions.subprocess.run", return_value=completed
        ) as mocked_run:
            result = acender_olhos()

        mocked_print.assert_called_once_with("Tool executada: acender_olhos()")
        self.assertEqual(
            mocked_run.call_args_list,
            [
                unittest.mock.call(
                    ["ros2", "topic", "pub", "--once", "/effectors/right_eye_leds", "nao_command_msgs/msg/RightEyeLeds", payload],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
                unittest.mock.call(
                    ["ros2", "topic", "pub", "--once", "/effectors/left_eye_leds", "nao_command_msgs/msg/LeftEyeLeds", payload],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
            ],
        )
        self.assertEqual(result, "Olhos acesos em azul.")

    def test_apagar_olhos_publishes_both_eye_commands(self):
        completed = Mock()
        payload = "{ colors: [{r: 0.0, g: 0.0, b: 0.0}, {r: 0.0, g: 0.0, b: 0.0}, {r: 0.0, g: 0.0, b: 0.0}, {r: 0.0, g: 0.0, b: 0.0}, {r: 0.0, g: 0.0, b: 0.0}, {r: 0.0, g: 0.0, b: 0.0}, {r: 0.0, g: 0.0, b: 0.0}, {r: 0.0, g: 0.0, b: 0.0}] }"

        with patch("builtins.print") as mocked_print, patch("src.tools.actions.shutil.which", return_value="/usr/bin/ros2"), patch(
            "src.tools.actions.subprocess.run", return_value=completed
        ) as mocked_run:
            result = apagar_olhos()

        mocked_print.assert_called_once_with("Tool executada: apagar_olhos()")
        self.assertEqual(
            mocked_run.call_args_list,
            [
                unittest.mock.call(
                    ["ros2", "topic", "pub", "--once", "/effectors/right_eye_leds", "nao_command_msgs/msg/RightEyeLeds", payload],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
                unittest.mock.call(
                    ["ros2", "topic", "pub", "--once", "/effectors/left_eye_leds", "nao_command_msgs/msg/LeftEyeLeds", payload],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
            ],
        )
        self.assertEqual(result, "Olhos apagados.")

    def test_mover_cabeca_esquerda_publishes_three_commands(self):
        completed = Mock()

        with patch("builtins.print") as mocked_print, patch("src.tools.actions.shutil.which", return_value="/usr/bin/ros2"), patch(
            "src.tools.actions.subprocess.run", return_value=completed
        ) as mocked_run:
            result = mover_cabeca_esquerda()

        mocked_print.assert_called_once_with("Tool executada: mover_cabeca_esquerda()")
        self.assertEqual(
            mocked_run.call_args_list,
            [
                unittest.mock.call(
                    [
                        "ros2",
                        "topic",
                        "pub",
                        "--once",
                        "/effectors/joint_stiffnesses",
                        "nao_command_msgs/msg/JointStiffnesses",
                        "{indexes: [0], stiffnesses: [0.5]}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
                unittest.mock.call(
                    [
                        "ros2",
                        "topic",
                        "pub",
                        "--once",
                        "/effectors/joint_positions",
                        "nao_command_msgs/msg/JointPositions",
                        "{indexes: [0], positions: [0.45]}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
                unittest.mock.call(
                    [
                        "ros2",
                        "topic",
                        "pub",
                        "--once",
                        "/effectors/joint_stiffnesses",
                        "nao_command_msgs/msg/JointStiffnesses",
                        "{indexes: [0], stiffnesses: [0.0]}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
            ],
        )
        self.assertEqual(result, "Cabeça movida para a esquerda.")

    def test_centralizar_cabeca_publishes_three_commands(self):
        completed = Mock()

        with patch("builtins.print") as mocked_print, patch("src.tools.actions.shutil.which", return_value="/usr/bin/ros2"), patch(
            "src.tools.actions.subprocess.run", return_value=completed
        ) as mocked_run:
            result = centralizar_cabeca()

        mocked_print.assert_called_once_with("Tool executada: centralizar_cabeca()")
        self.assertEqual(
            mocked_run.call_args_list,
            [
                unittest.mock.call(
                    [
                        "ros2",
                        "topic",
                        "pub",
                        "--once",
                        "/effectors/joint_stiffnesses",
                        "nao_command_msgs/msg/JointStiffnesses",
                        "{indexes: [0], stiffnesses: [0.5]}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
                unittest.mock.call(
                    [
                        "ros2",
                        "topic",
                        "pub",
                        "--once",
                        "/effectors/joint_positions",
                        "nao_command_msgs/msg/JointPositions",
                        "{indexes: [0], positions: [0.00]}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
                unittest.mock.call(
                    [
                        "ros2",
                        "topic",
                        "pub",
                        "--once",
                        "/effectors/joint_stiffnesses",
                        "nao_command_msgs/msg/JointStiffnesses",
                        "{indexes: [0], stiffnesses: [0.0]}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
            ],
        )
        self.assertEqual(result, "Cabeça centralizada.")

    def test_mover_cabeca_direita_publishes_three_commands(self):
        completed = Mock()

        with patch("builtins.print") as mocked_print, patch("src.tools.actions.shutil.which", return_value="/usr/bin/ros2"), patch(
            "src.tools.actions.subprocess.run", return_value=completed
        ) as mocked_run:
            result = mover_cabeca_direita()

        mocked_print.assert_called_once_with("Tool executada: mover_cabeca_direita()")
        self.assertEqual(
            mocked_run.call_args_list,
            [
                unittest.mock.call(
                    [
                        "ros2",
                        "topic",
                        "pub",
                        "--once",
                        "/effectors/joint_stiffnesses",
                        "nao_command_msgs/msg/JointStiffnesses",
                        "{indexes: [0], stiffnesses: [0.5]}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
                unittest.mock.call(
                    [
                        "ros2",
                        "topic",
                        "pub",
                        "--once",
                        "/effectors/joint_positions",
                        "nao_command_msgs/msg/JointPositions",
                        "{indexes: [0], positions: [-0.45]}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
                unittest.mock.call(
                    [
                        "ros2",
                        "topic",
                        "pub",
                        "--once",
                        "/effectors/joint_stiffnesses",
                        "nao_command_msgs/msg/JointStiffnesses",
                        "{indexes: [0], stiffnesses: [0.0]}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                ),
            ],
        )
        self.assertEqual(result, "Cabeça movida para a direita.")


if __name__ == "__main__":
    unittest.main()
