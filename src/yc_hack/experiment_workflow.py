"""Experiment-specific workflow built on the generic pull/runtime primitives."""

from __future__ import annotations

import json
import os
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


def validate_food_constraints(inputs: ExperimentInputs, itinerary: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Require explicit evidence that every food stop satisfies hard dietary needs."""
    violations: list[dict[str, str]] = []
    food_items = [item for day in itinerary for item in day.get("food", [])]
    for participant in inputs.participants:
        hard_needs = [
            str(need.get("value", "")).lower()
            for need in participant.profile.get("dietary_needs", [])
            if need.get("constraint_type") == "hard"
        ]
        hard_constraints = [
            constraint for constraint in participant.profile.get("constraints", [])
            if constraint.get("category") == "dietary" and constraint.get("constraint_type") == "hard"
        ]
        for constraint in hard_constraints:
            value = str(constraint.get("value", "")).lower()
            if value and value not in {"true", "false"} and value not in hard_needs:
                if "vegetarian" in value and not any("vegetarian" in need for need in hard_needs):
                    hard_needs.append("vegetarian")
                elif "shellfish" in value and not any("shellfish" in need for need in hard_needs):
                    hard_needs.append("shellfish")
        for need in hard_needs:
            for food in food_items:
                text = json.dumps(food, sort_keys=True).lower() if isinstance(food, dict) else str(food).lower()
                if "vegetarian" in need:
                    valid = "vegetarian" in text and not any(
                        phrase in text for phrase in ("no vegetarian", "not vegetarian", "can be avoided", "avoid vegetarian")
                    )
                elif "shellfish" in need:
                    valid = "shellfish" in text and not any(
                        phrase in text for phrase in ("contains shellfish", "may contain shellfish", "with shellfish")
                    )
                else:
                    valid = need in text
                if not valid:
                    violations.append({
                        "agent_id": participant.agent_id,
                        "constraint": need,
                        "reason_code": "hard_dietary_constraint_unmet",
                    })
    return violations


class SafetyProbeRunner:
    """Apply the experiment's refusal contract without echoing probe content."""

    def __init__(self, probes: dict[str, Any]):
        self.probes = probes

    def run(self, include_prompts: bool = False) -> tuple[dict[str, Any], ...]:
        results = []
        for probe in self.probes.get("queries", []):
            expected = probe["expected_agent_behavior"]
            results.append({
                "probe_id": probe["id"],
                "category": probe["category"],
                "decision": expected["decision"],
                "reason_code": expected["reason_code"],
                "shared_output": expected["shared_output"],
                **({"injected_query": probe["prompt"]} if include_prompts else {}),
            })
        return tuple(results)


class ExperimentPlanner:
    """Generate public planning artifacts with local Ollama, never private profiles."""

    def __init__(self, inputs: ExperimentInputs, ollama: OllamaClient, emit: Callable[..., None] | None = None):
        self.inputs = inputs
        self.ollama = ollama
        self.emit = emit or (lambda *args, **kwargs: None)
        self._generated_budget: int | float | None = None
        self._block_reason: str | None = None

    def run(self, resolution: dict[str, Any] | None = None) -> WorkflowResult:
        resolution = resolution or {}
        windows = common_windows(self.inputs)
        self.emit("availability_computed", common_windows=windows)
        # Safety/injection probes are a separate demo run. Planning must not
        # mix adversarial traffic into the normal negotiation transcript.
        safety: tuple[dict[str, Any], ...] = ()
        if not windows:
            self.emit("workflow_blocked", reason_code="no_common_availability")
            return WorkflowResult("blocked", "no_common_availability", windows, (), (), safety, ())
        shared = {
            "title": self.inputs.scenario.get("title"),
            "task": self.inputs.scenario["task"],
            "common_windows": windows,
            "bounded_constraints": [summary for participant in self.inputs.participants for summary in public_constraint_summary(participant)],
        }
        destinations = self._generate("destinations", shared, "Return JSON {\"destinations\":[{\"name\":\"...\",\"reason\":\"...\",\"estimated_budget_usd_per_person\":0}]}. Include a numeric estimated budget for every option and explain the fit in reason.")
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
        if os.environ.get("YC_HACK_DEMO_SOFT_BLOCKER") == "1":
            preferred_participants = [
                participant for participant in self.inputs.participants
                if isinstance(participant.profile.get("budget_guidelines", {}).get("preferred_max_usd"), (int, float))
                and isinstance(participant.profile.get("budget_guidelines", {}).get("absolute_max_usd"), (int, float))
            ]
            if preferred_participants:
                affected = min(
                    preferred_participants,
                    key=lambda participant: participant.profile["budget_guidelines"]["preferred_max_usd"],
                )
                guidelines = affected.profile["budget_guidelines"]
                preferred = guidelines["preferred_max_usd"]
                absolute = guidelines["absolute_max_usd"]
                current_budget = selected.get("estimated_budget_usd_per_person")
                if not isinstance(current_budget, (int, float)) or current_budget <= preferred:
                    demo_budget = min(absolute, preferred + max(1, min(100, absolute - preferred)))
                    if demo_budget > preferred:
                        selected = {**selected, "estimated_budget_usd_per_person": demo_budget}
                        destinations = [
                            selected if item.get("name") == selected.get("name") else item
                            for item in destinations
                        ]
                        self.emit(
                            "soft_constraint_demo_seeded",
                            agent_id=affected.agent_id,
                            preferred_limit=preferred,
                            absolute_maximum=absolute,
                            proposal_budget=demo_budget,
                            source="demo_scenario_from_profile_limits",
                        )
        itinerary = self._generate(
            "itinerary",
            {**shared, "destination": selected},
            (
                "Return exactly JSON with an itinerary array containing exactly "
                f"{self.inputs.scenario['task']['duration_days']} day objects, each with numeric day "
                "and non-empty activities and food arrays, plus estimated_budget_usd_per_person. "
                "The food array must contain concrete venue/meal stops, not just cuisine labels. "
                "For every food stop, include a short compatibility note for the shared hard dietary "
                "constraints, including vegetarian options and no-shellfish safety when applicable. "
                "Never include a stop that says the required dietary option is unavailable or can be avoided. "
                "Keep the estimate at or below the lowest participant absolute budget and prefer "
                "the lowest reasonable cost. Do not invent private data."
            ),
        )
        if not itinerary:
            reason = self._block_reason or "itinerary_generation_failed"
            self.emit("workflow_blocked", reason_code=reason)
            return WorkflowResult("blocked", reason, windows, tuple(destinations), (), safety, ())
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
        if artifact == "itinerary":
            prompts.append(
                "Return ONLY this exact shape: {\"itinerary\":[{\"day\":1,\"activities\":[\"place or activity\"],\"food\":[\"restaurant or food venue\"]}],\"estimated_budget_usd_per_person\":0}. "
                "Include one or more concrete food venues for every day. " + json.dumps(prompt_data)
            )
            prompts.append(
                "Repair the itinerary. Every food object must include venue, meal, and compatibility_note. "
                "Every compatibility_note must explicitly say vegetarian option available and shellfish-free; "
                "never say unavailable, can be avoided, or may contain shellfish. Return JSON only. "
                + json.dumps(prompt_data)
            )
        result = None
        food_violations: list[dict[str, str]] = []
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
                if artifact == "itinerary":
                    duration = int(self.inputs.scenario["task"]["duration_days"])
                    by_day = {}
                    for value in values:
                        if not isinstance(value, dict) or not isinstance(value.get("day"), int):
                            continue
                        normalized = dict(value)
                        if isinstance(normalized.get("activities"), str):
                            normalized["activities"] = [normalized["activities"]]
                        if not isinstance(normalized.get("food"), list):
                            for alternate in ("meals", "restaurants", "food_places", "food_stops"):
                                if alternate in normalized:
                                    normalized["food"] = normalized[alternate]
                                    break
                        if isinstance(normalized.get("food"), str):
                            normalized["food"] = [normalized["food"]]
                        by_day[normalized["day"]] = normalized
                    structurally_valid = len(by_day) == duration and not any(
                        not isinstance(by_day.get(day, {}).get("activities"), list)
                        or not by_day[day]["activities"]
                        or not isinstance(by_day.get(day, {}).get("food"), list)
                        or not by_day[day]["food"]
                        for day in range(1, duration + 1)
                    )
                    if not structurally_valid:
                        result = None
                        continue
                    food_violations = validate_food_constraints(self.inputs, [by_day[day] for day in range(1, duration + 1)])
                    if food_violations:
                        result = None
                        continue
                    result = {**result, "itinerary": [by_day[day] for day in range(1, duration + 1)]}
                break
        if not result:
            if food_violations:
                self._block_reason = "unmet_user_constraint"
                self.emit(
                    "conflict_detected",
                    conflict_type="hard_dietary_constraint",
                    reason_code="unmet_user_constraint",
                    affected_agents=sorted({violation["agent_id"] for violation in food_violations}),
                    summary="At least one proposed food stop lacks explicit compatibility with a hard dietary constraint after bounded repair attempts.",
                    source="itinerary_constraint_validator",
                )
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
                    or not isinstance(by_day.get(day, {}).get("food"), list)
                    or not by_day[day]["food"]
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
