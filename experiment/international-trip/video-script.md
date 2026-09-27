# Demo video input flow

1. Show the three user cards. Each card contains only user-related facts.
2. Open the separate October calendar view for each person and show meetings
   plus important dates.
3. Inject the synthetic PII and prompt-injection queries from
   `safety/injection-queries.json`. Show the personal agents refusing or
   redacting them while the shared trace keeps only bounded reason codes.
4. Create a no-common-availability or constraint-tradeoff case. Show the
   coordinator entering `blocked` state and asking the affected user for an
   explicit resolution.
5. Ask the AI coordinator to intersect availability and account for the task
   constraints in `scenario.json`.
6. Let the AI generate destination options, rank them, and create the
   itinerary.
7. Show the final AI output and any unresolved tradeoffs.

The recording should not imply a predetermined destination or itinerary: the
recommendations are produced by the AI agent during the demo.
