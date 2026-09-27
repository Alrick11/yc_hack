# Shared Agent Context

This document is the task-scoped context exchanged between the personal agents
and the consensus coordinator. It is a shared coordination record, not a dump
of anyone's private memory.

## Privacy boundary

- Personal preferences remain in the owning participant's GBrain memory.
- Agents share only task-relevant constraints, decisions, and bounded reasons.
- Do not copy raw preference profiles, private memories, credentials, or hidden
  chain-of-thought into this file.
- Memorable receives sanitized task traces and tool outcomes, not private
  profile contents or conversation transcripts.

## Task

- Task ID: `international-trip-demo`
- Objective: three personal agents plan and approve a five-day international trip
- Status: `validated`
- Context version: `0.7`
- Coordinator: local Ollama coordinator
- Participants: three personal agents
- Runtime model requirement: local Ollama
- Demo requirement: three-agent trip itinerary flow with a deterministic reset,
  visible shared rounds, and a finalized itinerary

## Shared facts

Facts that every participating agent may rely on for this task:

- The experiment input is `experiment/international-trip/scenario.json`.
- The participants are configured by the experiment and must remain data-driven;
  runtime code must not hardcode names, destinations, dates, or itinerary items.
- The current local model assignment is configurable through `YC_HACK_MODELS`.
- A validated run used `llama3.2:latest`, `qwen2.5-coder:1.5b`, and
  `deepseek-coder:6.7b`.

## Constraints

### Hard constraints

Conditions that must never be violated:

- All required agents must be available for the selected trip window.
- Dietary, accessibility/health-related, and absolute budget constraints remain
  hard unless the affected user explicitly approves an allowed change.
- No private profile, calendar, memory, credential, or sensitive query value
  may enter shared context or the event log.

### Soft preferences

Negotiable preferences that may influence proposal ranking:

- `unassigned`

## Proposal history

| Round | Proposal | Result | Bounded reasons | Next action |
|---|---|---|---|---|
| 1 | Generated destinations, common windows, and itinerary | approved by all three agents | bounded approval responses | finalized trip |

Use reason codes or short bounded explanations. Do not add private details
unless the owner explicitly authorizes sharing them for this task.

## Current decision

- Decision: `consensus_reached`
- Approved by: all three configured personal agents
- Decision rationale: the shared proposal passed the required approval gate
  without exposing private profile data
- Decided at: latest validated local Ollama run

## Unresolved questions

- Live injection probes still need to be executed through the agents.
- A deterministic blocked scenario and user-resolution replay still need to be
  added for the recording.

## Update protocol

1. The coordinator creates a new task and assigns a unique Task ID.
2. Each agent contributes only task-scoped, shareable context.
3. Every update increments the context version and records the round.
4. An agent may retract or revise its own contribution.
5. The coordinator records approvals explicitly; silence is not approval.
6. A task ends with `consensus_reached`, `blocked`, or `cancelled`.

## Agent communication model

Agents communicate through the coordinator's task store rather than directly
with one another. The runtime may use polling or long-polling; an agent reads
the latest public task state, evaluates it using private memory, and writes a
bounded contribution back to its own outbox.

The shared task state contains the task definition, proposal version, round,
bounded agent responses, unresolved conflicts, deadlines, and outcome. It must
not contain raw profiles, calendars, private memories, credentials, or private
reasoning.

Supported contribution types include `availability`, `constraint_summary`,
`proposal_evaluation`, `clarification_request`, and `approval`. Contributions
must identify the agent and round, and must use bounded reason codes.

## Consensus termination

The task reaches `consensus_reached` only when every required agent explicitly
approves the same proposal version, all hard constraints pass, and no
conditional response or clarification remains unresolved. Silence is never
approval.

The task reaches `blocked` when hard constraints conflict, a required agent
times out, the round limit is reached, an agent refuses for safety/privacy
reasons, or a required human decision is missing. The coordinator must expose
the blocking reason rather than silently relaxing a constraint.

## Integration notes

- All participant agents and the coordinator's agentic reasoning run through
  Ollama on the local machine. Provider/model names must be configurable by
  environment variables, with a documented default that runs on a laptop.
- The demo must not require cloud model inference. Network-backed integrations
  may enrich the experience but must have a visible degraded/offline mode.
- GBrain is the private preference and participant-memory layer.
- The coordinator should request structured decisions such as `approve`,
  `reject`, or `conditional`, plus a bounded reason code.
- Memorable can receive the sanitized negotiation trace after a completed task
  and return a reusable procedure for future similar tasks.
- Retrieved procedures are reference material and must be validated against the
  current task before they influence a decision.

## Implemented runtime

- `PullTaskStore` owns task state, agent inboxes, proposal versions, leases,
  bounded contributions, and terminal outcomes.
- `PullAgentWorker` claims one delivery, evaluates it with local Ollama and
  private memory, then submits a versioned contribution.
- `PullCoordinator` publishes proposals, waits for all required responses,
  requests revisions, and blocks on unavailable or unsafe agents.
- `JsonlEventLog` records task, proposal, claim, contribution, revision, and
  termination events without private profile content.
- `ExperimentPlanner` loads profiles/calendars, computes common availability,
  generates destinations and itineraries with Ollama, and creates explicit
  budget-approval gates.
- `LocalOllamaAgent` retries malformed responses and distinguishes hard
  constraint failures from soft preference tradeoffs.
- Approval tasks allow a bounded revision round; invalid, unsafe, timed-out,
  or unresolved responses still block.
- `proposal_published` events include the public proposal payload so the demo
  UI can show proposal changes between rounds.
- Proposal and destination events identify their source as the local Ollama
  coordinator; agent contributions identify the proposal version they reviewed.
- `conflict_detected`, `workflow_blocked`, and `user_action_required` events
  make conflict resolution and requests for additional user information
  visible in the shared conversation, with bounded summaries and permitted
  choices only.
- A negotiable budget blocker emits `soft_blocker_detected` and
  `user_approval_requested`; the coordinator calls the demo's
  `POST /api/user-approval` adapter, which returns an explicit `yes` for the
  mocked user. Approval is recorded before the proposal is sent to the agent
  approval gate. Missing or non-yes responses fail closed.
- CLI commands are `preflight`, `run`, `workflow`, `replay`, and `web`; `pull`
  is the default generic run mode and `push` remains available for comparison.
- `web` serves a dependency-free ChatGPT-style live workspace. Start and Reset
  controls launch or clear the configured workflow; coordinator and agent
  bubbles stream from the JSONL event log.
- The web server exposes `POST /api/user-approval` as a demo-only user adapter;
  it returns `{"decision":"yes"}` and must be replaced by a real user-facing
  approval service outside the demo.
- If `YC_HACK_MODELS` is not set, the workflow selects the first installed
  Ollama model and assigns it to all three agents for a repeatable laptop demo.
- `video-assets` uses optional Pillow support to generate title, round, and
  outcome cards from that same public event log for video editing.

## Validation status

- Local Ollama JSON smoke test: passed.
- Unit tests: passed, 11/11.
- Pull-mode end-to-end run: passed with three local Ollama models and reached
  `consensus_reached`, including a finalized five-day itinerary.
- Browser-controlled live run: passed through Start/Reset endpoints and
  reached `consensus_reached` with shared proposal and agent-contribution
  events visible in the conversation view.
- Mock user approval endpoint: passed; `POST /api/user-approval` returned an
  explicit `yes`, and the approval adapter mapped it to `approved`.
- An earlier three-model run blocked safely on invalid/conditional agent
  responses, confirming the fail-closed path.
- Replay output and a shared-event leakage scan passed; no raw participant
  profiles or sensitive probe values were emitted.
- Safety behavior is currently validated from the experiment fixtures. Live
  injection prompts through Ollama agents remain the next validation task.
- The same state machine still fail-closes on invalid responses, unsafe
  contributions, timeouts, unresolved approvals, and round limits.
- The browser timeline receives the public proposal payload, bounded agent
  responses, revisions, and terminal outcome; it never receives raw profiles.
- The browser conversation labels coordinator suggestions, agent reviews,
  safety refusals, conflicts, and user decisions separately. A workflow-level
  block is rendered as blocked and human-decision-required, not as idle or
  successful.
- The demo-only approval adapter is intentionally local and deterministic; it
  must be replaced by an authenticated user-facing service for production.

## Demo-video requirements

- Seed the same three participant profiles and task every time.
- Provide one command or button to reset and run the complete scenario.
- Show each agent's name, current round, decision, and bounded reason code.
- Show the shared task state without revealing private preference contents.
- Include a successful consensus path and a clearly labeled blocked/no-consensus
  outcome if the first proposal fails.
- Keep external calls bounded by timeouts and provide mock responses when GBrain
  or Memorable is unavailable, rate-limited, or not yet configured.
- Capture an audit timeline suitable for screen recording, with no API keys or
  private memory content displayed.

## Current next steps

1. Run real PII, health, and prompt-injection probes through the local agents.
2. Assert that every probe produces a bounded refusal/redaction and that the
   sensitive value is absent from shared events.
3. Add a deterministic blocked scenario and a user-resolution replay for the
   video.
4. Replace the demo approval adapter with a real authenticated user approval
   service for production use.
