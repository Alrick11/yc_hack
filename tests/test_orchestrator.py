import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from yc_hack.orchestrator import ConsensusOrchestrator
from yc_hack.protocol import AgentDecision, Proposal, TaskSpec


class FakeAgent:
    def __init__(self, agent_id, decisions):
        self.agent_id = agent_id
        self.decisions = iter(decisions)

    def decide(self, task, proposal):
        del task, proposal
        decision, reason = next(self.decisions)
        return AgentDecision(self.agent_id, decision, reason)


class OrchestratorTests(unittest.TestCase):
    def test_retries_until_all_agents_approve(self):
        agents = [
            FakeAgent("a", [("reject", "needs_revision"), ("approve", "ok")]),
            FakeAgent("b", [("approve", "ok"), ("approve", "ok")]),
            FakeAgent("c", [("approve", "ok"), ("approve", "ok")]),
        ]

        def proposals(task, round_number, previous):
            del task, previous
            return Proposal(round_number, {"round": round_number})

        result = ConsensusOrchestrator(agents, proposals).run(TaskSpec("t", "objective", max_rounds=2))
        self.assertEqual(result.status, "consensus_reached")
        self.assertEqual(result.proposal.round_number, 2)
        self.assertEqual(len(result.trace), 6)

    def test_no_consensus_is_explicit(self):
        agents = [FakeAgent("a", [("reject", "blocked"), ("reject", "blocked")])]
        result = ConsensusOrchestrator(agents, lambda t, r, p: Proposal(r, {})).run(
            TaskSpec("t", "objective", max_rounds=2)
        )
        self.assertEqual(result.status, "blocked")


if __name__ == "__main__":
    unittest.main()

