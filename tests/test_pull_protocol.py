import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from yc_hack.pull_protocol import Contribution, PullTaskStore


class PullProtocolTests(unittest.TestCase):
    def test_all_agents_pull_and_approve(self):
        store = PullTaskStore()
        task = store.create_task("task", ["a", "b", "c"], max_rounds=2)
        store.publish_proposal("task", {"version": 1})
        for agent_id in ("a", "b", "c"):
            delivery = store.pull("task", agent_id)
            self.assertIsNotNone(delivery)
            result = store.submit("task", Contribution(agent_id, 1, "approval", "approved", "ok", 1), delivery.delivery_id)
            self.assertEqual(result, "accepted")
        self.assertEqual(task.status, "consensus_reached")

    def test_silence_does_not_count_as_approval(self):
        store = PullTaskStore()
        task = store.create_task("task", ["a", "b", "c"], max_rounds=1)
        store.publish_proposal("task", {"version": 1})
        for agent_id in ("a", "b"):
            delivery = store.pull("task", agent_id)
            store.submit("task", Contribution(agent_id, 1, "approval", "approved", "ok", 1), delivery.delivery_id)
        self.assertEqual(task.status, "awaiting_agent_responses")
        self.assertNotEqual(task.status, "consensus_reached")

    def test_blocked_response_stops_task(self):
        store = PullTaskStore()
        task = store.create_task("task", ["a"], max_rounds=2)
        store.publish_proposal("task", {"version": 1})
        delivery = store.pull("task", "a")
        store.submit("task", Contribution("a", 1, "safety", "blocked", "privacy_boundary", 1), delivery.delivery_id)
        self.assertEqual(task.status, "blocked")


if __name__ == "__main__":
    unittest.main()

