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

- Task ID: `unassigned`
- Objective: `unassigned`
- Status: `draft`
- Context version: `0.3`
- Coordinator: `unassigned`
- Participants: three personal agents
- Runtime model requirement: local Ollama
- Demo requirement: three-agent trip itinerary flow with a deterministic reset

## Shared facts

Facts that every participating agent may rely on for this task:

- `unassigned`

## Constraints

### Hard constraints

Conditions that must never be violated:

- `unassigned`

### Soft preferences

Negotiable preferences that may influence proposal ranking:

- `unassigned`

## Proposal history

| Round | Proposal | Result | Bounded reasons | Next action |
|---|---|---|---|---|
| 0 | `unassigned` | `pending` | `unassigned` | `unassigned` |

Use reason codes or short bounded explanations. Do not add private details
unless the owner explicitly authorizes sharing them for this task.

## Current decision

- Decision: `none`
- Approved by: `none`
- Decision rationale: `unassigned`
- Decided at: `unassigned`

## Unresolved questions

- `unassigned`

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
- CLI commands are `preflight`, `run`, and `replay`; `pull` is the default run
  mode and `push` remains available for comparison.

## Validation status

- Local Ollama JSON smoke test: passed.
- Unit tests: passed.
- Pull-mode end-to-end run: completed with a replayable blocked outcome when
  the configured local agents did not reach consensus.
- Latest implementation commit: `e6c28cb`.

## Demo-video requirements

- Seed the same three participant profiles and task every time.
- Provide one command or button to reset and run the complete scenario.
- Show each agent's name, current round, decision, and bounded reason code.
- Make private-vs-shared context visible without revealing private preference
  contents.
- Include a successful consensus path and a clearly labeled blocked/no-consensus
  outcome if the first proposal fails.
- Keep external calls bounded by timeouts and provide mock responses when GBrain
  or Memorable is unavailable, rate-limited, or not yet configured.
- Capture an audit timeline suitable for screen recording, with no API keys or
  private memory content displayed.
