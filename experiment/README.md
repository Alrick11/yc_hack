# Experiment instructions

This folder owns the experiment details. The runtime deliberately does not
choose participant names, destinations, preferences, itinerary content, or
video narration.

## Configure

```bash
cp experiment/config.example.json experiment/config.json
```

Fill in the task objective, three participant IDs and profiles, shared task
context, and one proposal per negotiation round. Profiles are seeded into the
participant's private memory adapter and are never placed in the shared trace.

## Run

Start local Ollama and pull whichever model you want to use:

```bash
ollama serve
ollama pull <local-model>
PYTHONPATH=src OLLAMA_MODEL=<local-model> python -m yc_hack.demo
```

For the recording view, run the web timeline in a second terminal after the
runner has created its event path:

```bash
PYTHONPATH=src python -m yc_hack web --events .runtime/events/<session>.jsonl
```

To use a different config:

```bash
YC_HACK_EXPERIMENT_CONFIG=experiment/config.json \
  PYTHONPATH=src python -m yc_hack.demo
```

The same Ollama model may be used for all three agents. The coordinator runs
agents sequentially and emits only bounded decisions, reason codes, and round
metadata. GBrain and Memorable are optional; provider failure does not change
the orchestration protocol.

## Video checklist

- Keep experiment content in `config.json`, not in runtime code.
- Use a fresh run and a known local model.
- Show the round/proposal/decision timeline.
- Do not show profiles, raw prompts, API keys, or private memory output.
- Capture the final consensus and the sanitized procedure artifact.
- Include the existing safety-injection segment and show refusal/blocked
  reason codes in the shared timeline.
