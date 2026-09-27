"""Experiment execution, preflight, and replay services."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .agents import LocalOllamaAgent
from .config import ConfigError, load_experiment, validate_experiment
from .coordinator import LocalOllamaCoordinator
from .events import JsonlEventLog, read_events
from .experiment_workflow import ExperimentPlanner, load_inputs
from .ollama import OllamaClient
from .orchestrator import ConsensusOrchestrator
from .protocol import AgentSpec, Proposal, TaskSpec
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


def _request_user_approval(url: str | None, request: dict) -> str | None:
    """Ask the configured user-approval adapter; fail closed on any error."""
    if not url:
        return None
    body = json.dumps({
        "request_id": f"budget-{request['agent_id']}",
        "agent_id": request["agent_id"],
        "question": "Approve this small increase within your stated absolute maximum?",
        "preferred_limit": request.get("preferred_limit"),
        "absolute_maximum": request.get("absolute_maximum"),
        "incremental_amount": request.get("incremental_amount"),
    }).encode()
    try:
        call = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(call, timeout=3) as response:
            result = json.loads(response.read().decode())
        decision = str(result.get("decision", "")).lower()
        return "approved" if decision in {"yes", "approved", "approve"} else "declined"
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        return None


def workflow(config_path: str, events_path: str | None = None, resolution_path: str | None = None) -> int:
    try:
        inputs = load_inputs(config_path)
    except (OSError, KeyError, ValueError) as error:
        print(f"workflow_config_error={error}")
        return 2
    session_id = f"{inputs.scenario.get('title', 'workflow').lower().replace(' ', '-')}-{int(time.time())}"
    event_path = Path(events_path or f".runtime/events/{session_id}.jsonl")
    log = JsonlEventLog(event_path, session_id)
    resolution = {}
    if resolution_path:
        try:
            resolution = json.loads(Path(resolution_path).read_text())
        except (OSError, json.JSONDecodeError) as error:
            print(f"resolution_error={error}")
            return 2
    available_models = OllamaClient().models()
    configured_models = [name.strip() for name in os.environ.get("YC_HACK_MODELS", "").split(",") if name.strip()]
    # The browser demo should be repeatable on a laptop. If the user has not
    # assigned per-agent models, use the first installed Ollama model for all
    # three agents; YC_HACK_MODELS still enables explicit heterogeneous runs.
    model_names = configured_models or ([available_models[0]] * 3 if available_models else [])
    coordinator_model = os.environ.get("YC_HACK_COORDINATOR_MODEL") or (model_names[0] if model_names else None)
    result = ExperimentPlanner(inputs, OllamaClient(model=coordinator_model), log.emit).run(resolution)
    final_status = result.status
    approval_result = None
    if result.status == "proposal_ready":
        proposal = {
            "common_windows": result.common_windows,
            "destinations": result.destinations,
            "itinerary": result.itinerary,
            "budget_requests": result.budget_requests,
        }
        approval_resolution = dict(resolution)
        unresolved_budget = [request for request in result.budget_requests if approval_resolution.get(request["agent_id"]) != "approved"]
        if unresolved_budget:
            approval_question = "The coordinator found a soft budget blocker. May I use this option within your absolute maximum to preserve the group itinerary?"
            log.emit(
                "soft_blocker_detected",
                blocker_type="budget_preference",
                affected_agents=[request["agent_id"] for request in unresolved_budget],
                summary="A preferred budget is exceeded, but the requested amount remains within the affected user's explicit flexibility range.",
                source="coordinator_constraint_check",
            )
            for request in unresolved_budget:
                log.emit(
                    "user_approval_requested",
                    request_id=f"budget-{request['agent_id']}",
                    requested_from=request["agent_id"],
                    question=approval_question,
                    preferred_limit=request.get("preferred_limit"),
                    absolute_maximum=request.get("absolute_maximum"),
                    incremental_amount=request.get("incremental_amount"),
                    source="coordinator_outreach",
                )
                # Keep the public conversation compatible with older viewers
                # while the richer approval event is recorded for new ones.
                log.emit(
                    "user_action_required",
                    reason_code="soft_blocker_approval",
                    requested_from=request["agent_id"],
                    prompt=approval_question,
                    choices=["approve_budget_increase", "decline_budget_increase"],
                    source="coordinator_outreach",
                )
                decision = _request_user_approval(os.environ.get("YC_HACK_USER_APPROVAL_URL"), request)
                if decision:
                    approval_resolution[request["agent_id"]] = decision
                    log.emit(
                        "user_approval_received",
                        request_id=f"budget-{request['agent_id']}",
                        requested_from=request["agent_id"],
                        decision=decision,
                        source="mock_user_approval_api",
                    )
                    if decision == "approved":
                        log.emit(
                            "user_resolution_applied",
                            resolution_type="budget_increase",
                            agent_id=request["agent_id"],
                            decision="approved",
                            source="explicit_user_approval",
                        )
            unresolved_budget = [request for request in result.budget_requests if approval_resolution.get(request["agent_id"]) != "approved"]
        if unresolved_budget:
            final_status = "blocked"
            choices = ["approve_budget_increase", "decline_budget_increase", "choose_another_destination"]
            log.emit(
                "conflict_detected",
                conflict_type="budget_preference_conflict",
                reason_code="budget_approval_required",
                affected_agents=[request["agent_id"] for request in unresolved_budget],
                summary="The generated proposal exceeds a preferred budget. The affected user must decide whether the concrete benefit is worth the increase.",
                source="proposal_constraint_check",
            )
            log.emit("workflow_blocked", reason_code="budget_approval_required", requests=unresolved_budget)
            log.emit(
                "user_action_required",
                reason_code="budget_approval_required",
                requested_from=[request["agent_id"] for request in unresolved_budget],
                prompt="Please approve the increase, decline it, or choose another destination.",
                choices=choices,
            )
            print(f"user_action_required={json.dumps({'reason_code': 'budget_approval_required', 'choices': choices})}")
        else:
            task = TaskSpec(
                task_id=f"{inputs.scenario.get('title', 'workflow').lower().replace(' ', '-')}-approval",
                objective="Approve the generated trip proposal using private participant constraints.",
                max_rounds=2,
                shared_context={
                    **proposal,
                    "user_approvals": {
                        agent_id: decision for agent_id, decision in approval_resolution.items() if decision == "approved"
                    },
                },
            )
            brain = GBrainAdapter()
            for participant in inputs.participants:
                brain.remember(participant.agent_id, json.dumps(participant.profile, sort_keys=True))
            ollama = OllamaClient()
            specs = [AgentSpec(p.agent_id, "task-relevant private constraints", model_names[index] if index < len(model_names) else None) for index, p in enumerate(inputs.participants)]
            agents = [LocalOllamaAgent(spec, brain, ollama.with_model(spec.model)) for spec in specs]
            # Approval workers share one task store; it is the task authority.
            store = PullTaskStore(event_sink=log.emit)
            workers = [PullAgentWorker(task, store, agent) for agent in agents]
            approval_result = PullCoordinator(task, store, workers, lambda current, round_number, previous: proposal).run()
            final_status = approval_result.status
            if final_status == "blocked":
                choices = ["revise_proposal", "change_dates", "change_destination", "stop_planning"]
                log.emit(
                    "conflict_detected",
                    conflict_type="agent_constraint_conflict",
                    reason_code="agent_consensus_failed",
                    summary="At least one personal agent could not approve this proposal; the coordinator will not infer consent.",
                    source="agent_reviews",
                )
                log.emit(
                    "user_action_required",
                    reason_code="agent_consensus_failed",
                    prompt="Choose how to continue; no private constraint will be changed automatically.",
                    choices=choices,
                )
                print(f"user_action_required={json.dumps({'reason_code': 'agent_consensus_failed', 'choices': choices})}")
    elif result.status == "blocked":
        choices = ["add_date_range", "relax_soft_constraint", "change_destination", "stop_planning"]
        reason_code = result.reason_code or "workflow_blocked"
        log.emit(
            "conflict_detected",
            conflict_type="planning_input_conflict",
            reason_code=reason_code,
            summary="The coordinator needs an explicit user decision or more task information before it can continue.",
            source="workflow_validation",
        )
        log.emit(
            "user_action_required",
            reason_code=reason_code,
            prompt="Please provide more information or choose a permitted resolution.",
            choices=choices,
        )
        print(f"user_action_required={json.dumps({'reason_code': reason_code, 'choices': choices})}")
    print(f"session={session_id}")
    print(f"events={event_path}")
    print(f"workflow_status={final_status}")
    print(f"common_windows={json.dumps(result.common_windows)}")
    print(f"destinations={json.dumps(result.destinations)}")
    print(f"itinerary={json.dumps(result.itinerary)}")
    print(f"budget_requests={json.dumps(result.budget_requests)}")
    if final_status == "consensus_reached":
        selected_destination = result.destinations[0] if result.destinations else None
        selected_window = result.common_windows[0] if result.common_windows else None
        print(f"final_trip={json.dumps({'destination': selected_destination, 'window': selected_window, 'itinerary': result.itinerary})}")
    return 0 if final_status in {"proposal_ready", "consensus_reached"} else 1


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
