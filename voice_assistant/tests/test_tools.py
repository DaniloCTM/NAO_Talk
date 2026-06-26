from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.actions import acender_led, apagar_led, bateria, observar, sentar, levanta
from src.tools.registry import TOOL_DEFINITIONS, TOOL_REGISTRY


class ToolsTest(unittest.TestCase):
    def test_tool_registry_exposes_expected_tools(self):
        self.assertEqual(
            set(TOOL_REGISTRY),
            {"levanta", "sentar", "observar", "bateria", "acender_led", "apagar_led"},
        )
        self.assertIs(TOOL_REGISTRY["levanta"], levanta)
        self.assertIs(TOOL_REGISTRY["sentar"], sentar)
        self.assertIs(TOOL_REGISTRY["observar"], observar)
        self.assertIs(TOOL_REGISTRY["bateria"], bateria)
        self.assertIs(TOOL_REGISTRY["acender_led"], acender_led)
        self.assertIs(TOOL_REGISTRY["apagar_led"], apagar_led)

        definition_names = {item["function"]["name"] for item in TOOL_DEFINITIONS}
        self.assertEqual(
            definition_names,
            {"levanta", "sentar", "observar", "bateria", "acender_led", "apagar_led"},
        )

    def test_mock_actions_print_to_terminal(self):
        with patch("builtins.print") as mocked_print:
            result_levanta = levanta()
            result_sentar = sentar()
            result_observar = observar()

        mocked_print.assert_any_call("Mock action executada: levanta()")
        mocked_print.assert_any_call("Mock action executada: sentar()")
        mocked_print.assert_any_call("Mock action executada: observar()")
        self.assertEqual(result_levanta, "Ação levanta executada com sucesso.")
        self.assertEqual(result_sentar, "Ação sentar executada com sucesso.")
        self.assertEqual(result_observar, "Ação observar executada com sucesso.")

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
                "/effectors/chest_led",
                "nao_command_msgs/msg/ChestLed",
                "{ color: {r: 0.0, g: 0.0, b: 1.0}}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=3.0,
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
                "/effectors/chest_led",
                "nao_command_msgs/msg/ChestLed",
                "{ color: {r: 0.0, g: 0.0, b: 0.0}}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        self.assertEqual(result, "LED do peito apagado.")


if __name__ == "__main__":
    unittest.main()
