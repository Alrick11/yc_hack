import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from yc_hack.providers import GBrainAdapter, LocalPreferenceStore, MemorableAdapter


class Milestone0Tests(unittest.TestCase):
    def test_gbrain_fallback_is_scoped_by_agent(self):
        store = LocalPreferenceStore()
        adapter = GBrainAdapter(command="definitely-not-gbrain", fallback=store)
        adapter.remember("alice", "vegetarian")
        adapter.remember("ben", "japanese")
        self.assertEqual(adapter.recall("alice", "food"), ["vegetarian"])
        self.assertEqual(adapter.recall("ben", "food"), ["japanese"])

    def test_memorable_trace_is_sanitized_and_local(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter = MemorableAdapter(directory)
            result = adapter.record(
                "session-1",
                "choose a restaurant",
                [{"name": "agent_decision", "action": "approve", "ok": True,
                  "private_preference": "do not leak this"}],
            )
            self.assertEqual(result["mode"], "local-fallback")
            payload = json.loads(Path(directory, "session-1.json").read_text())
            self.assertNotIn("private_preference", json.dumps(payload))
            self.assertEqual(payload["tool_calls"][0]["result"], {"ok": True})


if __name__ == "__main__":
    unittest.main()

