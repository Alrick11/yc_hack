# YC Hack — Multi-Agent Consensus

Milestone 1 provides a generic three-agent consensus orchestrator for a local
Ollama experiment, with optional memory adapters for GBrain and Memorable. The
experiment content lives in `experiment/config.json`, not in the runtime.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m yc_hack.demo
```

To use local Ollama, start it in another terminal and pull a small model:

```bash
ollama serve
ollama pull llama3.2
OLLAMA_MODEL=llama3.2 python -m yc_hack.demo
```

The Python code uses only the standard library. Run from the repository root
with `PYTHONPATH=src` if the package is not installed:

```bash
PYTHONPATH=src python -m yc_hack.demo
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Providers

- GBrain is used as the private preference store when its CLI is available.
  Configure `GBRAIN_BIN` and, optionally, `GBRAIN_HOME`.
- Memorable is used for sanitized procedure traces when
  `MEMORABLE_API_KEY` is set. Without a key, the trace is written to the local
  runtime directory and the demo continues.
- Neither provider receives raw participant profiles from the coordinator.

## Milestone 2 commands

```bash
PYTHONPATH=src python -m yc_hack preflight
PYTHONPATH=src python -m yc_hack run --config experiment/international-trip/scenario.json
PYTHONPATH=src python -m yc_hack workflow --config experiment/international-trip/scenario.json
PYTHONPATH=src python -m yc_hack replay --events .runtime/events/<session>.jsonl
PYTHONPATH=src python -m yc_hack web \
  --config experiment/international-trip/scenario.json \
  --events .runtime/events/live.jsonl
PYTHONPATH=src python -m yc_hack video-assets --events .runtime/events/<session>.jsonl
```

The runner emits append-only JSONL events containing task, proposal, bounded
decision, and outcome metadata. Private profile content is never written to
the event stream.

The web command serves a live ChatGPT-style workspace with Start live demo and
Reset controls. It launches the local workflow, streams coordinator and agent
responses from the JSONL event log, and shows rounds, proposals, revisions,
and terminal outcomes. It requires no frontend dependencies.

For the demo's soft-blocker path, the server also exposes
`POST /api/user-approval`. It is a dummy user adapter that returns
`{"decision":"yes"}`; the coordinator calls it only for negotiable requests
such as a budget increase and records the explicit approval before continuing.

The `video-assets` command uses Pillow to generate title, round, and outcome
cards from the same public event log. Install the optional video dependency
with `python3 -m pip install -r requirements-video.txt`. The browser remains
the live product surface; Pillow adds recording overlays without recreating
or inventing agent activity.

The workflow command loads profiles and calendars, computes common availability,
runs safety refusals, asks local Ollama for destinations and an itinerary, and
emits budget approval gates without exposing private profile content.

## Pull protocol

`yc_hack.pull_protocol.PullTaskStore` provides the local pull-based contract:
agents claim deliveries, submit bounded contributions against a proposal
version, and are evaluated by an explicit termination state machine. Silence
does not approve a task; all required approvals are needed for success, while
blocked or unsafe contributions terminate the task safely.

## Demo recording

Use three configured participants and a known local model each run. The output
shows the agent, round, decision, bounded reason, and provider status without
printing private preference text. See `experiment/README.md` for the video
flow.
