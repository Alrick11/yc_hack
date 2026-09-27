"""Local pull-based task store and consensus termination state machine."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Contribution:
    agent_id: str
    round_number: int
    kind: str
    status: str
    reason_code: str
    proposal_version: int
    public_message: str = ""


@dataclass
class Delivery:
    delivery_id: str
    agent_id: str
    round_number: int
    proposal_version: int
    proposal: Any
    lease_until: float


@dataclass
class PullTask:
    task_id: str
    required_agents: tuple[str, ...]
    max_rounds: int
    status: str = "created"
    round_number: int = 0
    proposal_version: int = 0
    proposal: Any = None
    responses: dict[str, Contribution] = field(default_factory=dict)
    inboxes: dict[str, list[Delivery]] = field(default_factory=dict)
    active_leases: dict[str, Delivery] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


class PullTaskStore:
    """A deterministic local store; replace its persistence without changing the protocol."""

    def __init__(self, lease_seconds: float = 60.0, clock=time.time, event_sink=None):
        self.lease_seconds = lease_seconds
        self.clock = clock
        self.event_sink = event_sink
        self.tasks: dict[str, PullTask] = {}

    def create_task(self, task_id: str, agent_ids: list[str], max_rounds: int) -> PullTask:
        if not agent_ids or len(set(agent_ids)) != len(agent_ids):
            raise ValueError("task needs unique required agents")
        task = PullTask(task_id, tuple(agent_ids), max_rounds)
        task.status = "collecting_inputs"
        for agent_id in agent_ids:
            task.inboxes[agent_id] = []
        self.tasks[task_id] = task
        self._event(task, "task_created", agents=agent_ids)
        return task

    def publish_proposal(self, task_id: str, proposal: Any) -> PullTask:
        task = self.tasks[task_id]
        if task.status in {"consensus_reached", "blocked", "cancelled"}:
            raise ValueError(f"task is terminal: {task.status}")
        if task.round_number >= task.max_rounds:
            task.status = "blocked"
            self._event(task, "consensus_blocked", reason_code="round_limit")
            return task
        task.round_number += 1
        task.proposal_version += 1
        task.proposal = proposal
        task.responses.clear()
        task.status = "awaiting_agent_responses"
        for agent_id in task.required_agents:
            task.inboxes[agent_id].append(Delivery(
                str(uuid.uuid4()), agent_id, task.round_number, task.proposal_version,
                proposal, self.clock() + self.lease_seconds,
            ))
        self._event(task, "proposal_published", round=task.round_number, proposal_version=task.proposal_version)
        return task

    def pull(self, task_id: str, agent_id: str) -> Delivery | None:
        task = self.tasks[task_id]
        if agent_id not in task.required_agents or task.status != "awaiting_agent_responses":
            return None
        active = task.active_leases.get(agent_id)
        if active and active.lease_until > self.clock():
            return None
        if active:
            self._event(task, "agent_timeout", agent_id=agent_id, round=active.round_number)
        while task.inboxes[agent_id]:
            delivery = task.inboxes[agent_id].pop(0)
            if delivery.round_number == task.round_number:
                task.active_leases[agent_id] = delivery
                self._event(task, "agent_claimed", agent_id=agent_id, round=delivery.round_number)
                return delivery
        return None

    def submit(self, task_id: str, contribution: Contribution, delivery_id: str) -> str:
        task = self.tasks[task_id]
        delivery = task.active_leases.get(contribution.agent_id)
        if not delivery or delivery.delivery_id != delivery_id:
            return "rejected_invalid_lease"
        if delivery.lease_until <= self.clock():
            self._event(task, "agent_timeout", agent_id=contribution.agent_id, round=contribution.round_number)
            return "rejected_expired_lease"
        if contribution.round_number != task.round_number or contribution.proposal_version != task.proposal_version:
            return "rejected_stale_contribution"
        task.responses[contribution.agent_id] = contribution
        del task.active_leases[contribution.agent_id]
        self._event(task, "agent_contribution", agent_id=contribution.agent_id, round=contribution.round_number, kind=contribution.kind, status=contribution.status, reason_code=contribution.reason_code)
        if len(task.responses) == len(task.required_agents):
            self._evaluate(task)
        return "accepted"

    def _evaluate(self, task: PullTask) -> None:
        if all(response.status == "approved" for response in task.responses.values()):
            task.status = "consensus_reached"
            self._event(task, "consensus_reached", round=task.round_number, proposal_version=task.proposal_version)
            return
        if any(response.status in {"blocked", "unsafe"} for response in task.responses.values()):
            task.status = "blocked"
            self._event(task, "consensus_blocked", reason_code="agent_blocked", round=task.round_number)
            return
        if task.round_number >= task.max_rounds:
            task.status = "blocked"
            self._event(task, "consensus_blocked", reason_code="round_limit", round=task.round_number)
            return
        task.status = "revising"
        self._event(task, "revision_required", round=task.round_number)

    def _event(self, task: PullTask, event_type: str, **payload: Any) -> None:
        event = {"type": event_type, "task_id": task.task_id, **payload}
        task.events.append(event)
        if self.event_sink:
            self.event_sink(event_type, task_id=task.task_id, **payload)

    def expire_leases(self, task_id: str) -> None:
        task = self.tasks[task_id]
        for agent_id, delivery in list(task.active_leases.items()):
            if delivery.lease_until <= self.clock():
                del task.active_leases[agent_id]
                task.status = "blocked"
                self._event(task, "consensus_blocked", reason_code="agent_timeout", agent_id=agent_id)

    def block(self, task_id: str, reason_code: str) -> None:
        task = self.tasks[task_id]
        if task.status not in {"consensus_reached", "blocked", "cancelled"}:
            task.status = "blocked"
            self._event(task, "consensus_blocked", reason_code=reason_code)
