from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tools.actions import observar, sentar, levanta
from src.tools.registry import TOOL_DEFINITIONS, TOOL_REGISTRY


class ToolsTest(unittest.TestCase):
    def test_tool_registry_exposes_expected_tools(self):
        self.assertEqual(set(TOOL_REGISTRY), {"levanta", "sentar", "observar"})
        self.assertIs(TOOL_REGISTRY["levanta"], levanta)
        self.assertIs(TOOL_REGISTRY["sentar"], sentar)
        self.assertIs(TOOL_REGISTRY["observar"], observar)

        definition_names = {item["function"]["name"] for item in TOOL_DEFINITIONS}
        self.assertEqual(definition_names, {"levanta", "sentar", "observar"})

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


if __name__ == "__main__":
    unittest.main()
