"""Personal-agent runtime: private memory in, bounded decision out."""

from __future__ import annotations

import json
import re
from typing import Protocol

from .ollama import OllamaClient
from .protocol import AgentDecision, AgentSpec, Proposal, TaskSpec


class PreferenceMemory(Protocol):
    def recall(self, agent_id: str, query: str) -> list[str]: ...


def parse_json_object(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        result = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


class LocalOllamaAgent:
    """Runs a participant decision locally and redacts private context at the boundary."""

    def __init__(self, spec: AgentSpec, memory: PreferenceMemory, ollama: OllamaClient):
        self.spec = spec
        self.memory = memory
        self.ollama = ollama

    def decide(self, task: TaskSpec, proposal: Proposal) -> AgentDecision:
        private_context = self.memory.recall(self.spec.agent_id, self.spec.memory_query)
        prompt = {
            "task": task.objective,
            "shared_context": task.shared_context,
            "proposal": proposal.content,
            "private_context": private_context,
            "response_schema": {
                "decision": "approve | reject | conditional",
                "reason_code": "short non-sensitive code",
                "public_message": "short message safe for the coordinator",
            },
        }
        if not self.ollama.available():
            return AgentDecision(self.spec.agent_id, "conditional", "model_unavailable", "model unavailable")
        result = None
        for _ in range(2):
            try:
                result = parse_json_object(self.ollama.chat(
                    "You are a private personal agent. Never reveal private context. Return JSON only.",
                    json.dumps(prompt),
                    json_mode=True,
                ))
            except (OSError, KeyError, TypeError, ValueError):
                result = None
            if result:
                break
        decision_value = str(result.get("decision", "")).strip().lower() if result else ""
        if decision_value not in {"approve", "reject", "conditional"}:
            return AgentDecision(self.spec.agent_id, "conditional", "invalid_agent_response", "invalid response")
        return AgentDecision(
            self.spec.agent_id,
            decision_value,
            str(result.get("reason_code", "unspecified"))[:80],
            str(result.get("public_message", ""))[:240],
        )
