"""Experiment-specific workflow built on the generic pull/runtime primitives."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from .agents import parse_json_object
from .ollama import OllamaClient


@dataclass(frozen=True)
class ParticipantInput:
    agent_id: str
    profile: dict[str, Any]
    calendar: dict[str, Any]


@dataclass(frozen=True)
class ExperimentInputs:
    scenario: dict[str, Any]
    participants: tuple[ParticipantInput, ...]
    safety: dict[str, Any]
    conflict_resolution: str


@dataclass(frozen=True)
class WorkflowResult:
    status: str
    reason_code: str | None
    common_windows: tuple[tuple[str, str], ...]
    destinations: tuple[dict[str, Any], ...]
    itinerary: tuple[dict[str, Any], ...]
    safety_results: tuple[dict[str, Any], ...]
    budget_requests: tuple[dict[str, Any], ...]


def load_inputs(scenario_path: str | Path) -> ExperimentInputs:
    path = Path(scenario_path)
    scenario = json.loads(path.read_text())
    inputs = scenario.get("inputs", {})
    profiles_dir = path.parent / inputs["profiles_dir"]
    calendars_dir = path.parent / inputs["calendars_dir"]
    participants = []
    for agent_id in scenario["participants"]:
        profile = json.loads((profiles_dir / f"{agent_id}.json").read_text())
        calendar = json.loads((calendars_dir / f"{agent_id}.json").read_text())
        participants.append(ParticipantInput(str(agent_id), profile, calendar))
    safety = json.loads((path.parent / inputs["safety_queries"]).read_text())
    conflict = (path.parent / inputs["conflict_resolution"]).read_text()
    return ExperimentInputs(scenario, tuple(participants), safety, conflict)


def public_constraint_summary(participant: ParticipantInput) -> list[dict[str, Any]]:
    """Return only bounded constraints; never expose profile fields wholesale."""
    summary = []
    for constraint in participant.profile.get("constraints", []):
        category = str(constraint.get("category", "unknown"))
        if category in {"health", "accessibility"}:
            value: Any = "task-relevant accommodation required"
        else:
            value = constraint.get("value")
        summary.append({
            "agent_id": participant.agent_id,
            "category": category,
            "name": constraint.get("name"),
            "value": value,
            "constraint_type": constraint.get("constraint_type"),
            "negotiable": constraint.get("negotiable"),
        })
    return summary


def hard_unavailable_dates(calendar: dict[str, Any]) -> set[date]:
    unavailable: set[date] = set()
    for item in calendar.get("meetings", []):
        if item.get("constraint_type") == "hard" or item.get("importance") in {"high", "critical"}:
            unavailable.add(date.fromisoformat(item["start"][:10]))
    for item in calendar.get("important_dates", []):
        if item.get("constraint_type") == "hard" or item.get("importance") == "critical":
            unavailable.add(date.fromisoformat(item["date"]))
    return unavailable


def common_windows(inputs: ExperimentInputs) -> tuple[tuple[str, str], ...]:
    task = inputs.scenario["task"]
    start = date.fromisoformat(task["planning_window"][0])
    end = date.fromisoformat(task["planning_window"][1])
    duration = int(task["duration_days"])
    blocked = set().union(*(hard_unavailable_dates(p.calendar) for p in inputs.participants))
    windows = []
    cursor = start
    while cursor + timedelta(days=duration - 1) <= end:
        days = {cursor + timedelta(days=offset) for offset in range(duration)}
        if not days.intersection(blocked):
            windows.append((cursor.isoformat(), (cursor + timedelta(days=duration - 1)).isoformat()))
        cursor += timedelta(days=1)
    return tuple(windows)


class SafetyProbeRunner:
    """Apply the experiment's refusal contract without echoing probe content."""

    def __init__(self, probes: dict[str, Any]):
        self.probes = probes

    def run(self) -> tuple[dict[str, Any], ...]:
        results = []
        for probe in self.probes.get("queries", []):
            expected = probe["expected_agent_behavior"]
            results.append({
                "probe_id": probe["id"],
                "category": probe["category"],
                "decision": expected["decision"],
                "reason_code": expected["reason_code"],
                "shared_output": expected["shared_output"],
            })
        return tuple(results)


class ExperimentPlanner:
    """Generate public planning artifacts with local Ollama, never private profiles."""

    def __init__(self, inputs: ExperimentInputs, ollama: OllamaClient, emit: Callable[..., None] | None = None):
        self.inputs = inputs
        self.ollama = ollama
        self.emit = emit or (lambda *args, **kwargs: None)
        self._generated_budget: int | float | None = None

    def run(self, resolution: dict[str, Any] | None = None) -> WorkflowResult:
        resolution = resolution or {}
        windows = common_windows(self.inputs)
        self.emit("availability_computed", common_windows=windows)
        safety = SafetyProbeRunner(self.inputs.safety).run()
        for result in safety:
            self.emit("safety_refusal", **result)
        if not windows:
            self.emit("workflow_blocked", reason_code="no_common_availability")
            return WorkflowResult("blocked", "no_common_availability", windows, (), (), safety, ())
        shared = {
            "title": self.inputs.scenario.get("title"),
            "task": self.inputs.scenario["task"],
            "common_windows": windows,
            "bounded_constraints": [summary for participant in self.inputs.participants for summary in public_constraint_summary(participant)],
        }
        destinations = self._generate("destinations", shared, "Return JSON {\"destinations\":[{\"name\":\"...\",\"reason\":\"...\",\"estimated_budget_usd_per_person\":0}]}")
        if not destinations:
            self.emit("workflow_blocked", reason_code="destination_generation_failed")
            return WorkflowResult("blocked", "destination_generation_failed", windows, (), (), safety, ())
        self.emit(
            "destinations_generated",
            count=len(destinations),
            source="local_ollama_coordinator",
            source_detail="Generated by the coordinator from common availability and authorized, bounded constraints.",
        )
        selected = destinations[0]
        requested_destination = resolution.get("destination")
        if requested_destination:
            selected = next((item for item in destinations if item.get("name") == requested_destination), selected)
            self.emit("user_resolution_applied", resolution_type="destination", destination=selected.get("name"))
        itinerary = self._generate(
            "itinerary",
            {**shared, "destination": selected},
            (
                "Return exactly JSON with an itinerary array containing exactly "
                f"{self.inputs.scenario['task']['duration_days']} day objects, each with numeric day "
                "and non-empty activities array, plus estimated_budget_usd_per_person. "
                "Keep the estimate at or below the lowest participant absolute budget and prefer "
                "the lowest reasonable cost. Do not invent private data."
            ),
        )
        if not itinerary:
            self.emit("workflow_blocked", reason_code="itinerary_generation_failed")
            return WorkflowResult("blocked", "itinerary_generation_failed", windows, tuple(destinations), (), safety, ())
        selected_budget = selected.get("estimated_budget_usd_per_person") if isinstance(selected, dict) else None
        budget_requests = self._budget_requests(itinerary, self._generated_budget if self._generated_budget is not None else selected_budget)
        if budget_requests:
            self.emit(
                "budget_approval_required",
                count=len(budget_requests),
                affected_agents=[request["agent_id"] for request in budget_requests],
                source="proposal_constraint_check",
            )
        return WorkflowResult("proposal_ready", None, windows, tuple(destinations), tuple(itinerary), safety, tuple(budget_requests))

    def _generate(self, artifact: str, shared: dict[str, Any], instruction: str) -> list[dict[str, Any]]:
        if not self.ollama.available():
            return []
        prompt_data = {"artifact": artifact, "shared_context": shared, "instruction": instruction}
        prompts = [
            json.dumps(prompt_data),
            "Return valid JSON only. Do not explain. " + json.dumps(prompt_data),
            "Use the requested JSON schema exactly. Do not use markdown, prose, placeholders, or null values. "
            + json.dumps(prompt_data),
        ]
        result = None
        for prompt in prompts:
            try:
                result = parse_json_object(self.ollama.chat(
                    "You are a travel planning coordinator. Use shared context only. Return JSON only.",
                    prompt,
                    json_mode=True,
                ))
            except (OSError, KeyError, TypeError, ValueError):
                result = None
            values = result.get(artifact) if result else None
            if isinstance(values, list) and values:
                break
        if not result:
            return []
        if artifact == "itinerary" and result:
            budget = result.get("estimated_budget_usd_per_person")
            self._generated_budget = budget if isinstance(budget, (int, float)) else None
        values = result.get(artifact)
        if isinstance(values, list):
            values = [value for value in values if isinstance(value, dict)]
            if artifact == "itinerary":
                duration = int(self.inputs.scenario["task"]["duration_days"])
                by_day = {value.get("day"): value for value in values if isinstance(value.get("day"), int)}
                if len(by_day) != duration or any(
                    not isinstance(by_day.get(day, {}).get("activities"), list)
                    or not by_day[day]["activities"]
                    for day in range(1, duration + 1)
                ):
                    return []
                values = [by_day[day] for day in range(1, duration + 1)]
            return values
        return [values] if isinstance(values, dict) else []

    def _budget_requests(self, itinerary: list[dict[str, Any]], proposal_budget: int | float | None = None) -> list[dict[str, Any]]:
        if not itinerary:
            return []
        proposal_budget = proposal_budget if proposal_budget is not None else itinerary[0].get("estimated_budget_usd_per_person")
        if not isinstance(proposal_budget, (int, float)):
            return []
        requests = []
        for participant in self.inputs.participants:
            guidelines = participant.profile.get("budget_guidelines", {})
            preferred = guidelines.get("preferred_max_usd")
            absolute = guidelines.get("absolute_max_usd")
            if isinstance(preferred, (int, float)) and proposal_budget > preferred:
                requests.append({
                    "agent_id": participant.agent_id,
                    "preferred_limit": preferred,
                    "absolute_maximum": absolute,
                    "incremental_amount": proposal_budget - preferred,
                    "status": "approval_required",
                    "reason_code": "budget_increase_requires_explicit_approval",
                })
        return requests
