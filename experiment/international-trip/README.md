# Three Friends, One International Trip

This folder contains input data for the YC hackathon demo. The AI trip agent
is expected to inspect the three user profiles and their separate fake
October calendars, find compatible dates within October, and generate destination and itinerary
recommendations in another session.

No destination, dates, itinerary, or recommendation is hardcoded here.

## Data layout

- `profiles/` contains only user-related information: identity, work, dietary
  needs, budget, travel preferences, health/accessibility notes, and social
  preferences.
- `calendars/` contains fake October meetings and important dates. Every item
  is labeled `hard` or `soft`; calendar data is intentionally separate from the
  user profile data.
- `safety/injection-queries.json` contains synthetic PII and prompt-injection
  probes plus expected refusal behavior.
- `conflict-resolution.md` describes blocked states and user-resolution
  choices when agents cannot safely reach agreement.
- `scenario.json` defines the task, participants, constraints, input folders,
  and the outputs the AI agent should produce.

Hard constraints must be satisfied or the coordinator reports `blocked`.
Soft constraints can be traded off during consensus, but the affected user and
the tradeoff must be shown.

The profile `constraints` list is the authoritative cross-domain model. It
covers more than calendar availability: dietary restrictions,
accessibility/health needs, budget, transportation, lodging, activities, pace,
location, and social preferences. Each entry includes a category, value,
`constraint_type`, and negotiation rule.

All names and events are fictional fixtures for recording.

## Demo input

Pass this folder to the AI coordinator session as its input. The coordinator
should read `scenario.json`, then load the matching profile and calendar files.
This fixture intentionally stops before destination selection and itinerary
generation.

Each profile includes a preferred budget, an absolute maximum, and a small
flexibility guideline. If a strong option exceeds a user's preferred budget,
the coordinator may contact that specific user with the exact increase and
benefit. The user's explicit approval is required before the shared budget is
updated.

The runtime workflow consumes this folder directly:

```bash
PYTHONPATH=src python -m yc_hack workflow \
  --config experiment/international-trip/scenario.json
```

To assign three local models to the three personal agents:

```bash
YC_HACK_MODELS=llama3.2:latest,qwen2.5-coder:1.5b,deepseek-coder:6.7b \
  PYTHONPATH=src python -m yc_hack workflow \
  --config experiment/international-trip/scenario.json
```

If the workflow blocks, it prints explicit user choices. Supply an approved
resolution only after the affected user responds:

```bash
YC_HACK_MODELS=llama3.2:latest,qwen2.5-coder:1.5b,deepseek-coder:6.7b \
  PYTHONPATH=src python -m yc_hack workflow \
  --config experiment/international-trip/scenario.json \
  --resolution experiment/international-trip/resolution.json
```

The resolution file may select one of the generated destinations without
silently changing any participant constraint:

```json
{"destination": "Paris, France"}
```

Budget and hard-constraint exceptions still require explicit affected-user
approval and remain blocked when the proposed value exceeds an absolute limit.

It computes common availability, emits privacy-safe constraint summaries, runs
the synthetic safety probes, and asks local Ollama to generate destinations and
an itinerary. Budget overages become explicit approval requests; they are not
automatically accepted.

## Safety and escalation segment

The demo should inject the safety probes after showing the profile and calendar
views. Each personal agent should refuse or redact the request, emit only a
bounded reason code, and keep the sensitive value out of the shared trace.
Then show a deliberately blocked planning case. The coordinator should expose
the conflict and ask the affected user to choose how to resolve it; it should
not silently relax a critical date, health-related need, or privacy boundary.
