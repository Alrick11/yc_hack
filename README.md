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
PYTHONPATH=src python -m yc_hack replay --events .runtime/events/<session>.jsonl
```

The runner emits append-only JSONL events containing task, proposal, bounded
decision, and outcome metadata. Private profile content is never written to
the event stream.

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
