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
        prompts = [
            json.dumps(prompt),
            json.dumps({
                "private_context": private_context,
                "proposal": proposal.content,
                    "instruction": (
                        "Evaluate only your private hard constraints. Approve when all hard constraints "
                        "are satisfied, even if soft preferences are imperfect. Use conditional only for "
                        "a soft preference that needs a visible tradeoff. Reject only for a hard constraint, "
                        "privacy/safety issue, or missing required proposal field. For a hard constraint, "
                        "start reason_code with hard_. Return exactly one JSON "
                    "object with decision approve, reject, or conditional; reason_code; public_message."
                ),
            }),
            json.dumps({
                "private_context": private_context,
                "proposal": proposal.content,
                    "instruction": (
                        "Return one JSON object and nothing else. Required keys: decision, reason_code, "
                        "public_message. decision must be exactly approve, reject, or conditional. "
                        "Use a reason_code beginning hard_ when rejecting a hard constraint. "
                    "Approve if all hard constraints fit; soft preferences are not blockers."
                ),
            }),
        ]
        valid_result = None
        for prompt_text in prompts:
            try:
                candidate = parse_json_object(self.ollama.chat(
                    "You are a private personal agent. Never reveal private context. Return JSON only.",
                    prompt_text,
                    json_mode=True,
                ))
            except (OSError, KeyError, TypeError, ValueError):
                candidate = None
            candidate_decision = str(candidate.get("decision", "")).strip().lower() if candidate else ""
            if candidate and candidate_decision in {"approve", "reject", "conditional"}:
                valid_result = candidate
                # A first-pass conditional can be a formatting/understanding miss.
                # Give the compact contract prompt one chance to produce a definitive
                # decision, while preserving conditional if it is repeated.
                if candidate_decision != "conditional":
                    break
                result = candidate
            else:
                result = None
        if valid_result:
            result = valid_result
        decision_value = str(result.get("decision", "")).strip().lower() if result else ""
        if decision_value not in {"approve", "reject", "conditional"}:
            return AgentDecision(self.spec.agent_id, "conditional", "invalid_agent_response", "invalid response")
        return AgentDecision(
            self.spec.agent_id,
            decision_value,
            str(result.get("reason_code", "unspecified"))[:80],
            str(result.get("public_message", ""))[:240],
        )
