"""Load experiment configuration without embedding experiment-specific content."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .protocol import AgentSpec, TaskSpec


class ConfigError(ValueError):
    pass


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read JSON config {path}: {error}") from error


def load_experiment(path: str | Path) -> tuple[TaskSpec, list[AgentSpec], dict[str, Any], dict[str, str]]:
    """Return task, agent specs, raw config, and private profile seed values."""
    source = Path(path)
    raw = _read_json(source)
    if "objective" in raw:
        return _load_flat(source, raw)
    if "task" in raw and "participants" in raw:
        return _load_scenario(source, raw)
    raise ConfigError("config must contain either objective or task + participants")


def _load_flat(source: Path, raw: dict[str, Any]):
    participants = raw.get("participants")
    if not isinstance(participants, list) or not participants:
        raise ConfigError("participants must be a non-empty list")
    agents: list[AgentSpec] = []
    profiles: dict[str, str] = {}
    for participant in participants:
        if not isinstance(participant, dict):
            raise ConfigError("each participant must be an object")
        agent_id = str(participant.get("agent_id", "")).strip()
        if not agent_id:
            raise ConfigError("each participant needs agent_id")
        agents.append(AgentSpec(agent_id, str(participant.get("memory_query", "task preferences")), participant.get("model")))
        profiles[agent_id] = str(participant.get("profile", ""))
    task = TaskSpec(str(raw.get("task_id", source.stem)), str(raw["objective"]), int(raw.get("max_rounds", 3)), dict(raw.get("shared_context", {})))
    return task, agents, raw, profiles


def _load_scenario(source: Path, raw: dict[str, Any]):
    participant_ids = raw["participants"]
    if not isinstance(participant_ids, list) or not participant_ids:
        raise ConfigError("participants must be a non-empty list")
    task_data = raw["task"]
    objective = json.dumps(task_data, sort_keys=True)
    task = TaskSpec(str(source.parent.name), objective, int(raw.get("max_rounds", 3)), {"title": raw.get("title", "")})
    profiles_dir = source.parent / raw.get("inputs", {}).get("profiles_dir", "profiles")
    agents: list[AgentSpec] = []
    profiles: dict[str, str] = {}
    for participant_id in participant_ids:
        agent_id = str(participant_id)
        profile_path = profiles_dir / f"{agent_id}.json"
        profile = _read_json(profile_path)
        agents.append(AgentSpec(agent_id, "task-relevant private preferences, constraints, and availability"))
        profiles[agent_id] = json.dumps(profile, sort_keys=True)
    return task, agents, raw, profiles


def validate_experiment(path: str | Path) -> list[str]:
    errors: list[str] = []
    try:
        task, agents, raw, profiles = load_experiment(path)
        if len(agents) != 3:
            errors.append(f"expected exactly 3 participants, found {len(agents)}")
        if task.max_rounds < 1:
            errors.append("max_rounds must be positive")
        if len(set(agent.agent_id for agent in agents)) != len(agents):
            errors.append("participant agent_id values must be unique")
        if any(not profiles.get(agent.agent_id) for agent in agents):
            errors.append("every participant needs a non-empty private profile")
        if not raw.get("proposal_rounds") and raw.get("proposal_strategy", "ollama") not in {"ollama", "static"}:
            errors.append("proposal_strategy must be ollama or static")
    except ConfigError as error:
        errors.append(str(error))
    return errors

