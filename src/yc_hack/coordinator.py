"""Local Ollama proposal generation using shared context only."""

from __future__ import annotations

import json

from .agents import parse_json_object
from .ollama import OllamaClient
from .protocol import AgentDecision, Proposal, TaskSpec


class LocalOllamaCoordinator:
    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    def __call__(self, task: TaskSpec, round_number: int, previous: tuple[AgentDecision, ...]) -> Proposal:
        prompt = {
            "objective": task.objective,
            "shared_context": task.shared_context,
            "round": round_number,
            "previous_bounded_decisions": [
                {"agent_id": d.agent_id, "decision": d.decision, "reason_code": d.reason_code}
                for d in previous
            ],
            "response_schema": {"proposal": "complete task proposal using shared information only"},
        }
        if not self.ollama.available():
            return Proposal(round_number, {"status": "model_unavailable", "round": round_number})
        result = None
        for _ in range(2):
            try:
                result = parse_json_object(self.ollama.chat(
                    "You are a consensus coordinator. Never request or infer private profiles. Return JSON only.",
                    json.dumps(prompt),
                    json_mode=True,
                ))
            except (OSError, KeyError, TypeError, ValueError):
                result = None
            if result:
                break
        return Proposal(round_number, result.get("proposal") if result and "proposal" in result else {"status": "invalid_coordinator_response"})
