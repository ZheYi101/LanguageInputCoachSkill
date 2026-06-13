---
name: english-input-coach
description: |
  Use when the user already has English input materials as text, such as video transcripts,
  subtitles, or articles, and wants Codex to turn them into structured learning sessions.
  Best for Chinese-speaking learners who want lessons driven by their real input instead of
  generic textbook content. Supports two explicit tracks in v1: live_chat for conversational
  transcripts and article_reading for continuous written text. Also use when the user wants
  corrections on their exercise answers from a prior lesson generated from the same input.
---

# English Input Coach

把学习者已经接触过的英文输入，变成一轮可执行、可纠错、可沉淀的学习闭环。

This skill converts English input that the learner already consumed into a teachable loop:

1. Anchor the scene and intention of the input
2. Highlight high-value chunks or vocabulary
3. Force retrieval and noticing
4. Push contextual output
5. Update a lightweight profile delta from the learner's errors

## Always Load The Right Reference

Use this table before doing anything substantial.

| Situation | Must load |
| --- | --- |
| Validate minimum fields or decide whether the input is in scope | `references/input-contract.md` |
| A persistent `learning_root` exists or any long-term state will be read or written | `references/state-schema.md` |
| The input is raw `.srt`, subtitle text, transcript dump, or noisy copied text | `references/text-normalization.md` |
| Cleaned material must be cut into teachable units | `references/segmentation-policy.md` |
| Build a lesson for a transcript, stream, subtitle, or casual spoken excerpt | `references/track-live-chat.md` |
| Build a lesson for an article, essay, blog post, or continuous written passage | `references/track-article-reading.md` |
| The user comes back to study or review from a persistent workspace | `references/review-policy.md` |
| Correct learner answers and update the learning snapshot | `references/profile-schema.md` |
| Audit whether the lesson structure is grounded in the intended pedagogy | `references/pedagogy.md` |
| Check whether a generated lesson or correction pass is good enough | `references/validation-rubric.md` |

## When to use

Use this skill when:

- The user provides English text from a transcript, subtitle file, or article
- The user wants to learn from their own input instead of generic material
- The user wants contextualized vocabulary/chunk practice
- The user sends answers to exercises and wants correction plus next-step guidance

Do not use this skill for:

- Subtitle downloading, OCR, or ASR
- Beginner language instruction from zero
- General proofreading unrelated to an input passage
- Technical explainers as a separate track in v1

## Required input contract

Before teaching, validate the minimum contract from [references/input-contract.md](references/input-contract.md).

The caller should provide:

- `input_type`: `transcript` or `article`
- `track`: `live_chat` or `article_reading`
- `title`
- `text`

Optional fields:

- `learner_language` default `zh-CN`
- `source_url`
- `creator_or_channel`
- `watched_or_read` default `true`
- `material_type`
- `learning_root`

If `track` is missing, ask the user to choose. Do not auto-classify in v1.

If `learning_root` is present, switch to persistent workspace behavior using [references/state-schema.md](references/state-schema.md).

## Workflow

### Session start checklist for persistent mode

If `learning_root` exists or the user expects long-term storage:

1. Read `references/state-schema.md`.
2. Read `.language-coach/config.json` and `.language-coach/learner_profile.json`.
3. Query the workspace state before teaching:
   - last session
   - overdue review pressure
   - whether the material is already imported
   - whether cleaned segments already exist
4. If review pressure is high, summarize it first using `summary_first` behavior from `references/review-policy.md`.
5. Do not dump detailed review items by default.

### Mode A: Ingest material into workspace

Use this mode when the user first sends raw material and wants it stored for later learning.

1. Validate the input contract.
2. If `learning_root` is missing, ask for it or stay in one-off mode.
3. Read `references/state-schema.md`.
4. Write the raw material into the workspace and register it in the DB.
5. If the input is raw or noisy, normalize it before anything else.
6. Store the cleaned result and segment metadata for future sessions.

### Mode B: Build a lesson from input or from a stored segment

1. Validate the input contract.
2. If the input is raw or noisy, normalize it first using [references/text-normalization.md](references/text-normalization.md).
3. If the text is cleaned but not segmented, apply [references/segmentation-policy.md](references/segmentation-policy.md).
4. Read [references/pedagogy.md](references/pedagogy.md) only if you need to justify or audit the method.
5. Read the track guide:
   - `live_chat` -> [references/track-live-chat.md](references/track-live-chat.md)
   - `article_reading` -> [references/track-article-reading.md](references/track-article-reading.md)
6. If the normalized text is still too long for one useful session, choose a representative slice from the cleaned text and say what you selected.
7. Produce the lesson in this fixed order:
   - `Scene Capsule`
   - `High-Value Chunks / Vocab`
   - `Comprehension Check`
   - `Error-Prone Rewrite`
   - `Contextual Output`
   - `Profile Delta + Review Candidates`
8. If `learning_root` is active, save:
   - lesson artifact
   - session row
   - review items
   - profile events
9. Keep explanations concise and actionable. The goal is a session the learner can actually do.

### Mode C: Review learner answers from a prior lesson

Use this mode when the user replies with answers to `Comprehension Check`, `Error-Prone Rewrite`, or `Contextual Output`.

1. Re-anchor the targets from the prior lesson.
2. Correct the learner's answers directly and concretely.
3. Prioritize pattern-level errors over one-off typos.
4. Explain what changed and why, especially:
   - subject choice
   - adjective vs. verb structure
   - fixed chunk integrity
   - logical connectors
   - register mismatch
5. If `learning_root` is active, write:
   - feedback artifact
   - session completion or follow-up session
   - review item updates
   - profile events
6. End with an updated `Profile Delta + Review Candidates`.

### Mode D: Review mode

Use this mode when the user comes back to study and the workspace already has history.

1. Read `references/review-policy.md`.
2. Query the workspace for:
   - days since last session
   - overdue review pressure
   - current priority categories
3. Start with a summary, not a long item dump.
4. Let the agent choose whether today should be:
   - short review first
   - new content first
   - mixed mode
5. Only reveal detailed items if the user asks.

## Output contract

Always preserve the six-section structure. Use the field expectations from [references/profile-schema.md](references/profile-schema.md).

### Scene Capsule

- 4 to 6 sentences
- Chinese-led explanation
- Must explain what is happening in the source so the later language points have context

### High-Value Chunks / Vocab

- `live_chat`: prefer reusable chunks over isolated words
- `article_reading`: combine key terms and reusable written expressions
- For each item include:
  - source meaning in context
  - why it is worth learning
  - a common misuse or pitfall

### Comprehension Check

- At least 3 short items
- Prefer short answer, matching, or scenario judgment
- Do not pad with low-value multiple choice

### Error-Prone Rewrite

- At least 3 items
- Must target likely production failures for the track

### Contextual Output

- `live_chat`: 4 to 6 spoken-style sentences in the original scene
- `article_reading`: one 80 to 150 word summary, paraphrase, or stance rewrite
- Require reuse of at least 2 to 3 target items

### Profile Delta + Review Candidates

Output only the current learning delta, not a full permanent profile.

## Track-specific references

- Read [references/track-live-chat.md](references/track-live-chat.md) for VTuber, stream, and casual transcript lessons.
- Read [references/track-article-reading.md](references/track-article-reading.md) for continuous text, arguments, and article-based lessons.
- Read [references/state-schema.md](references/state-schema.md) for persistent workspace rules.
- Read [references/segmentation-policy.md](references/segmentation-policy.md) for material-aware slicing.
- Read [references/review-policy.md](references/review-policy.md) for summary-first review behavior.
- Read [references/validation-rubric.md](references/validation-rubric.md) when evaluating whether a generated lesson or correction pass is good enough.

## Important constraints

- Do not teach directly from raw subtitle noise when a cleaned lesson text can be prepared first.
- For transcripts and subtitles, cleaning is mandatory before target extraction and exercise design.
- Do not apply one segmentation strategy to all material types.
- Do not fragment a livestream or article until the original scene or argument becomes unusable.
- In persistent mode, do not bypass workspace state reads and writes.
- In review mode, do not dump all overdue items by default; summarize first and let the agent choose the agenda.
- Do not claim the method is scientifically proven to be optimal.
- Use research only to justify the structure, not to overstate certainty.
- Do not drift into generic textbook instruction. Stay grounded in the provided input.
- Do not return huge inventories of vocabulary. Select for reuse and leverage.
- Do not turn `Profile Delta` into a personality judgment. It is a learning-state snapshot.
