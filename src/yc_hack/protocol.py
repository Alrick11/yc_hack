"""Provider-neutral protocol types for multi-agent consensus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str
    memory_query: str
    model: str | None = None


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    objective: str
    max_rounds: int = 3
    shared_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Proposal:
    round_number: int
    content: Any


@dataclass(frozen=True)
class AgentDecision:
    agent_id: str
    decision: str
    reason_code: str
    public_message: str = ""


@dataclass(frozen=True)
class ConsensusResult:
    status: str
    proposal: Proposal | None
    decisions: tuple[AgentDecision, ...]
    trace: tuple[dict[str, Any], ...]

