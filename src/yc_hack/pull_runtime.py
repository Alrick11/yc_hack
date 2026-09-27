"""Workers and coordinator for the local pull-based execution model."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from .agents import LocalOllamaAgent
from .protocol import AgentDecision, Proposal, TaskSpec
from .pull_protocol import Contribution, PullTask, PullTaskStore


class PullAgentWorker:
    def __init__(self, task: TaskSpec, store: PullTaskStore, agent: LocalOllamaAgent):
        self.task = task
        self.store = store
        self.agent = agent

    def poll_once(self) -> str:
        delivery = self.store.pull(self.task.task_id, self.agent.spec.agent_id)
        if delivery is None:
            return "no_delivery"
        proposal = Proposal(delivery.round_number, delivery.proposal)
        decision = self.agent.decide(self.task, proposal)
        contribution = Contribution(
            agent_id=decision.agent_id,
            round_number=delivery.round_number,
            kind="proposal_evaluation",
            status=_contribution_status(decision),
            reason_code=decision.reason_code,
            proposal_version=delivery.proposal_version,
            public_message=decision.public_message,
        )
        return self.store.submit(self.task.task_id, contribution, delivery.delivery_id)


def _contribution_status(decision: AgentDecision) -> str:
    if decision.decision == "approve":
        return "approved"
    if decision.decision == "reject" and decision.reason_code.startswith((
        "hard_", "unmet_", "constraint_violation", "missing_required", "budget_hard"
    )):
        return "blocked"
    if decision.reason_code.startswith(("privacy", "safety", "unsafe")):
        return "blocked"
    return "needs_revision"


class PullCoordinator:
    """Coordinates pull workers without directly passing private context."""

    def __init__(self, task: TaskSpec, store: PullTaskStore, workers: Sequence[PullAgentWorker], proposal_factory: Callable):
        self.task = task
        self.store = store
        self.workers = tuple(workers)
        self.proposal_factory = proposal_factory

    def run(self) -> PullTask:
        self.store.create_task(self.task.task_id, [worker.agent.spec.agent_id for worker in self.workers], self.task.max_rounds)
        self.store.publish_proposal(self.task.task_id, self.proposal_factory(self.task, 1, ()))
        while self.store.tasks[self.task.task_id].status not in {"consensus_reached", "blocked", "cancelled"}:
            task_state = self.store.tasks[self.task.task_id]
            if task_state.status == "awaiting_agent_responses":
                made_progress = False
                for worker in self.workers:
                    made_progress = worker.poll_once() != "no_delivery" or made_progress
                    if task_state.status in {"consensus_reached", "blocked"}:
                        break
                if not made_progress:
                    self.store.block(self.task.task_id, "agent_unavailable")
            elif task_state.status == "revising":
                previous = tuple(
                    AgentDecision(response.agent_id, "approve" if response.status == "approved" else "reject", response.reason_code, response.public_message)
                    for response in task_state.responses.values()
                )
                proposal = self.proposal_factory(self.task, task_state.round_number + 1, previous)
                self.store.publish_proposal(self.task.task_id, proposal)
            else:
                self.store.expire_leases(self.task.task_id)
        return self.store.tasks[self.task.task_id]
