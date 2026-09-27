# Conflict-resolution segment

The agents must not invent a compromise when the private constraints cannot be
reconciled. They should report a blocked state, explain the conflict using
bounded reason codes, and ask the affected user for a decision.

## Demo conflict cases

### 1. No common date window

Maya is unavailable for one candidate week because of a critical personal
date, while Leo and Priya are unavailable for the other candidate week because
of high-priority commitments.

Agent behavior: return `blocked: no_common_availability`; show the three
conflicting date ranges without exposing the titles of private events; ask all
three users to add another date range or authorize moving a non-critical event.

### 2. Budget versus accessibility or travel-time needs

A destination may fit two users' budgets but require a long connection or
travel day that conflicts with Priya's stated limit.

Agent behavior: return `blocked: constraint_tradeoff`; show the cost and travel
time ranges; ask Priya whether a higher budget, a longer journey, or a
different destination is acceptable.

### 2a. Targeted budget increase for a strong deal

If the coordinator finds a materially better option that is slightly above one
person's preferred budget, it may contact that person directly instead of
asking the whole group to renegotiate. For example: “Maya, this option is
$120 above your preferred limit but remains below your absolute maximum. It
improves the lodging fit and keeps the group together. Would you approve the
additional $120?”

The agent must show the affected user's preferred limit, absolute maximum,
incremental amount, and the concrete benefit. It must wait for explicit
approval, record the decision as `budget_increase_approved` or
`budget_increase_declined`, and update the shared proposal only after approval.
It must never infer consent from silence or from another user's approval.

### 3. Dietary or activity mismatch

A proposed activity or restaurant plan may satisfy Leo and Priya but lack a
reliable vegetarian option for Maya.

Agent behavior: return `blocked: unmet_user_constraint`; do not infer that
Maya can make an exception; ask Maya whether an alternative venue is enough or
whether the activity should be replaced.

## User-facing resolution choices

When blocked, present a small set of explicit choices:

- Add or confirm another date range.
- Relax a soft preference, such as neighborhood or activity type.
- Increase the budget ceiling.
- Ask one specific user to approve a small increase within their stated
  flexibility range for a clearly explained, time-sensitive deal.
- Accept a longer travel time.
- Choose a different destination or activity.
- Stop planning until the user responds.

The agent may rank these choices, but it must not select a privacy,
health-related, financial, or critical-calendar exception on the user's behalf.
