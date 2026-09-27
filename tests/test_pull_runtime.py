import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from yc_hack.protocol import AgentDecision, AgentSpec, Proposal, TaskSpec
from yc_hack.pull_protocol import PullTaskStore
from yc_hack.pull_runtime import PullAgentWorker, PullCoordinator


class FakeAgent:
    def __init__(self, agent_id, decisions):
        self.spec = AgentSpec(agent_id, "preferences")
        self.decisions = iter(decisions)

    def decide(self, task, proposal):
        del task, proposal
        decision, reason = next(self.decisions)
        return AgentDecision(self.spec.agent_id, decision, reason)


class PullRuntimeTests(unittest.TestCase):
    def test_workers_pull_and_revision_reaches_consensus(self):
        task = TaskSpec("task", "objective", max_rounds=2)
        store = PullTaskStore()
        workers = [
            PullAgentWorker(task, store, FakeAgent("a", [("reject", "needs_revision"), ("approve", "ok")])),
            PullAgentWorker(task, store, FakeAgent("b", [("approve", "ok"), ("approve", "ok")])),
        ]

        def proposal_factory(current_task, round_number, previous):
            del current_task, previous
            return {"round": round_number}

        result = PullCoordinator(task, store, workers, proposal_factory).run()
        self.assertEqual(result.status, "consensus_reached")
        self.assertEqual(result.proposal, {"round": 2})
        self.assertEqual([event["type"] for event in result.events].count("agent_claimed"), 4)


if __name__ == "__main__":
    unittest.main()

