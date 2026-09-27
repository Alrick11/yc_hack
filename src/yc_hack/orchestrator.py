"""Round-based consensus orchestration with a narrow shared-context boundary."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .protocol import AgentDecision, ConsensusResult, Proposal, TaskSpec


ProposalFactory = Callable[[TaskSpec, int, Sequence[AgentDecision]], Proposal]


class ConsensusOrchestrator:
    def __init__(self, agents: Sequence[object], proposal_factory: ProposalFactory, event_sink: Callable[..., Any] | None = None):
        self.agents = tuple(agents)
        self.proposal_factory = proposal_factory
        self.event_sink = event_sink

    def _emit(self, event_type: str, **payload: Any) -> None:
        if self.event_sink:
            self.event_sink(event_type, **payload)

    def run(self, task: TaskSpec) -> ConsensusResult:
        self._emit("task_started", task_id=task.task_id, objective=task.objective, agent_count=len(self.agents))
        previous: tuple[AgentDecision, ...] = ()
        trace: list[dict] = []
        proposal: Proposal | None = None
        for round_number in range(1, task.max_rounds + 1):
            proposal = self.proposal_factory(task, round_number, previous)
            self._emit("proposal_created", round=round_number, proposal=proposal.content)
            decisions = tuple(agent.decide(task, proposal) for agent in self.agents)
            for decision in decisions:
                trace.append({
                    "name": "agent_decision",
                    "agent_id": decision.agent_id,
                    "round": round_number,
                    "action": decision.decision,
                    "reason_code": decision.reason_code,
                    "ok": decision.decision == "approve",
                })
                self._emit("agent_decision", **trace[-1])
            if all(decision.decision == "approve" for decision in decisions):
                self._emit("consensus_reached", round=round_number)
                return ConsensusResult("consensus_reached", proposal, decisions, tuple(trace))
            previous = decisions
            self._emit("round_blocked", round=round_number)
        self._emit("consensus_blocked", rounds=task.max_rounds)
        return ConsensusResult("blocked", proposal, previous, tuple(trace))
