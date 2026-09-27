import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from yc_hack.experiment_workflow import SafetyProbeRunner, common_windows, load_inputs, public_constraint_summary


ROOT = Path(__file__).parents[1]
SCENARIO = ROOT / "experiment/international-trip/scenario.json"


class ExperimentWorkflowTests(unittest.TestCase):
    def test_loads_three_private_inputs_and_common_windows(self):
        inputs = load_inputs(SCENARIO)
        self.assertEqual(len(inputs.participants), 3)
        windows = common_windows(inputs)
        self.assertTrue(windows)
        self.assertTrue(all(len(window) == 2 for window in windows))

    def test_public_summary_redacts_health_and_accessibility_values(self):
        inputs = load_inputs(SCENARIO)
        summary = public_constraint_summary(next(p for p in inputs.participants if p.agent_id == "priya"))
        accessibility = next(item for item in summary if item["category"] == "accessibility")
        self.assertEqual(accessibility["value"], "task-relevant accommodation required")

    def test_safety_results_contain_no_probe_prompt(self):
        inputs = load_inputs(SCENARIO)
        results = SafetyProbeRunner(inputs.safety).run()
        serialized = str(results)
        self.assertNotIn("passport number", serialized)
        self.assertTrue(all(result["decision"] in {"refuse", "refuse_or_redact"} for result in results))


if __name__ == "__main__":
    unittest.main()

