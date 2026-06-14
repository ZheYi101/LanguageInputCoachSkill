# Review Policy

Use this reference when the user returns to study in a persistent workspace.

## Default user-facing behavior

The default review opening is `summary_first`.

That means:

- do not dump a long list of review items on the user
- summarize what has been neglected
- suggest the 1 to 3 most important review directions
- only show detailed item lists when the user asks

## Internal vs external granularity

Internal tracking can be fine-grained:

- chunks
- vocabulary
- error patterns
- article connectors
- paraphrase weaknesses

But the default user-facing summary should stay coarse:

- "live-chat chunks are overdue"
- "fixed chunk integrity has decayed"
- "article paraphrase connectors need review"

## Review opening template

At session start, summarize:

- how long it has been since the last session in this language
- which categories have accumulated the most review pressure
- what the recommended agenda is for today

Do not list dozens of items unless the user explicitly asks for details.

## Agenda selection

Choose the review agenda from:

- overdue pressure
- low stability
- recent repeated failure
- high reuse value
- proximity to current learning goals

Recommend:

- short review first if pressure is high
- new content first if review pressure is low
- mixed mode if both are moderate

## Item detail policy

If the user asks for specifics, show only a small slice:

- 3 to 5 items by default
- grouped by category when possible

Do not show hundreds of lines of review items in normal flow.

## User controls

The user must be able to:

- delete an item
- ignore an item
- pause a category
- archive a source
- say a learned item is not useful

These actions should update tracking state without losing historical trace.

## Review writeback expectations

When a real review pass is completed in persistent mode:

- create or update a `review` session in `sessions`
- update the reviewed `review_items`
- set `last_reviewed_at`
- move `due_at`
- adjust `interval_days`
- adjust `stability`
- adjust `priority_score`
- mark clearly retired items as `mastered` only when appropriate

v1 does not need a full SRS implementation, but it must at least distinguish outcomes like:

- `again`
- `hard`
- `good`
- `easy`
- `mastered`
