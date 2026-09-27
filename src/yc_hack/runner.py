"""Experiment execution, preflight, and replay services."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .agents import LocalOllamaAgent
from .config import ConfigError, load_experiment, validate_experiment
from .coordinator import LocalOllamaCoordinator
from .events import JsonlEventLog, read_events
from .ollama import OllamaClient
from .orchestrator import ConsensusOrchestrator
from .protocol import Proposal
from .providers import GBrainAdapter, MemorableAdapter
from .pull_protocol import PullTaskStore
from .pull_runtime import PullAgentWorker, PullCoordinator


def default_config() -> str:
    return os.environ.get("YC_HACK_EXPERIMENT_CONFIG", "experiment/international-trip/scenario.json")


def preflight(config_path: str) -> int:
    errors = validate_experiment(config_path)
    ollama = OllamaClient()
    print(f"config={config_path}")
    print(f"config_status={'ok' if not errors else 'invalid'}")
    for error in errors:
        print(f"config_error={error}")
    print(f"ollama={'available' if ollama.available() else 'unavailable'} url={ollama.url}")
    print(f"ollama_models={json.dumps(ollama.models())}")
    brain = GBrainAdapter()
    print(f"gbrain_cli={'available' if brain.available else 'unavailable'} command={brain.command}")
    memorable = MemorableAdapter()
    print(f"memorable={'api' if memorable.enabled else 'local-fallback'}")
    return 1 if errors else 0


def run(config_path: str, events_path: str | None = None, mode: str = "pull") -> int:
    try:
        task, agent_specs, raw, profiles = load_experiment(config_path)
    except ConfigError as error:
        print(f"config_error={error}")
        return 2
    errors = validate_experiment(config_path)
    if errors:
        for error in errors:
            print(f"config_error={error}")
        return 2
    ollama = OllamaClient()
    brain = GBrainAdapter()
    for agent_id, profile in profiles.items():
        brain.remember(agent_id, profile)
    agents = [LocalOllamaAgent(spec, brain, ollama.with_model(spec.model)) for spec in agent_specs]
    static_proposals = list(raw.get("proposal_rounds", []))
    coordinator = LocalOllamaCoordinator(ollama)

    def proposal_factory(current_task, round_number, previous):
        if static_proposals:
            return Proposal(round_number, static_proposals[min(round_number - 1, len(static_proposals) - 1)])
        return coordinator(current_task, round_number, previous)

    session_id = f"{task.task_id}-{int(time.time())}"
    event_path = Path(events_path or f".runtime/events/{session_id}.jsonl")
    log = JsonlEventLog(event_path, session_id)
    if mode == "pull":
        store = PullTaskStore(event_sink=log.emit)
        workers = [PullAgentWorker(task, store, agent) for agent in agents]
        def pull_proposal_factory(current_task, round_number, previous):
            proposal = proposal_factory(current_task, round_number, previous)
            return proposal.content if isinstance(proposal, Proposal) else proposal

        pull_result = PullCoordinator(task, store, workers, pull_proposal_factory).run()
        result_status = pull_result.status
        trace = [event for event in pull_result.events if event.get("type") == "agent_contribution"]
    elif mode == "push":
        result = ConsensusOrchestrator(agents, proposal_factory, log.emit).run(task)
        result_status = result.status
        trace = list(result.trace)
    else:
        print(f"invalid_mode={mode}")
        return 2
    memorable = MemorableAdapter()
    procedure = memorable.record(session_id, task.objective, trace)
    print(f"session={session_id}")
    print(f"events={event_path}")
    print(f"mode={mode}")
    print(f"outcome={result_status}")
    print(f"procedure={json.dumps(procedure, sort_keys=True)}")
    return 0 if result_status == "consensus_reached" else 1


def replay(events_path: str) -> int:
    try:
        events = read_events(events_path)
    except (OSError, ValueError) as error:
        print(f"replay_error={error}")
        return 2
    for event in events:
        event_type = event.get("type")
        if event_type in {"task_started", "task_created"}:
            print(f"task={event.get('task_id')} agents={event.get('agent_count', event.get('agents'))}")
        elif event_type in {"proposal_created", "proposal_published"}:
            print(f"round={event.get('round')} proposal_created")
        elif event_type in {"agent_decision", "agent_contribution"}:
            print(f"round={event.get('round')} agent={event.get('agent_id')} decision={event.get('action', event.get('status'))} reason={event.get('reason_code')}")
        elif event_type in {"consensus_reached", "consensus_blocked"}:
            print(f"outcome={event_type}")
    return 0
