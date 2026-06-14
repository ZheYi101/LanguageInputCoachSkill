# State Schema

This reference defines the long-term learning workspace for `input-driven-language-coach`.

Use it whenever:

- a `learning_root` already exists
- the user wants to store materials before studying
- the user wants persistent profile, review, or lesson history
- the skill is about to write long-term state

## Design principle

Use hybrid storage:

- files for materials and lesson artifacts
- SQLite for queryable state and review progress
- JSON for readable workspace config and the current learner profile snapshot

Do not collapse everything into one large profile file.

## Workspace layout

```text
{learning_root}/
├── .language-coach/
│   ├── config.json
│   ├── learner_profile.json
│   ├── state.db
│   ├── migrations/
│   └── scripts/
├── languages/
│   ├── en/
│   │   ├── raw/
│   │   ├── cleaned/
│   │   ├── segments/
│   │   ├── lessons/
│   │   ├── sessions/
│   │   └── exports/
│   └── ja/
```

## `config.json`

Purpose:

- workspace-level configuration
- schema version
- review behavior defaults
- path conventions

Suggested shape:

```json
{
  "schema_version": 1,
  "learner_id": "default",
  "default_language": "en",
  "default_feedback_language": "zh-CN",
  "auto_write": true,
  "review_policy": {
    "mode": "summary_first",
    "max_focus_groups": 3,
    "max_item_details_on_demand": 5
  },
  "paths": {
    "languages_dir": "languages",
    "coach_dir": ".language-coach"
  },
  "created_at": "2026-06-13T12:00:00+08:00",
  "updated_at": "2026-06-13T12:00:00+08:00"
}
```

## `learner_profile.json`

Purpose:

- current snapshot only
- readable summary for agent startup
- rebuilt from DB history when needed

Suggested shape:

```json
{
  "schema_version": 1,
  "learner_id": "default",
  "native_language": "zh-CN",
  "active_languages": ["en"],
  "preferences": {
    "feedback_language": "zh-CN",
    "auto_write": true
  },
  "language_profiles": {
    "en": {
      "baseline_summary": null,
      "comprehension_strengths": [],
      "output_fragilities": [],
      "reusable_chunks": [],
      "recurring_vocab_gaps": [],
      "track_bias": [],
      "recent_priorities": [],
      "last_updated_at": null
    }
  },
  "created_at": "2026-06-13T12:00:00+08:00",
  "updated_at": "2026-06-13T12:00:00+08:00"
}
```

## SQLite tables

### `schema_meta`

- `key`
- `value`

Use to store DB schema version and maintenance metadata.

### `sources`

One row per imported material.

- `id`
- `language`
- `material_type`
- `track`
- `title`
- `source_url`
- `creator`
- `raw_path`
- `cleaned_path`
- `imported_at`
- `status`

### `segments`

One row per teachable segment cut from a cleaned source.

- `id`
- `source_id`
- `material_type`
- `track`
- `segment_index`
- `segment_path`
- `start_ref`
- `end_ref`
- `context_before_summary`
- `context_after_summary`
- `scene_or_argument_summary`
- `created_at`
- `status`

### `sessions`

One row per learning or review session.

- `id`
- `language`
- `track`
- `session_type`
- `source_id`
- `segment_id`
- `lesson_path`
- `answers_path`
- `feedback_path`
- `started_at`
- `finished_at`
- `status`

Recommended `session_type` values in v1:

- `lesson`
- `review`
- `feedback`

### `review_items`

Fine-grained review state. Internal tracking can be detailed even if user-facing review remains summary-first.

- `id`
- `language`
- `track`
- `review_category`
- `item_type`
- `content`
- `normalized_key`
- `source_id`
- `segment_id`
- `first_seen_at`
- `last_seen_at`
- `last_reviewed_at`
- `due_at`
- `interval_days`
- `stability`
- `priority_score`
- `status`

Minimum review writeback behavior:

- set `last_reviewed_at`
- set the next `due_at`
- adjust `interval_days`
- adjust `stability`
- adjust `priority_score`
- optionally promote an item to `mastered`

### `profile_events`

Evidence log for profile changes.

- `id`
- `language`
- `session_id`
- `event_type`
- `signal`
- `evidence`
- `strength`
- `created_at`

### `user_actions`

User-controlled overrides and deletions.

- `id`
- `target_type`
- `target_id`
- `action_type`
- `reason`
- `created_at`

Typical `action_type` values:

- `set_status:ignored`
- `set_status:paused`
- `set_status:deleted`
- `set_status:mastered`
- `archive`

## Status enums

### `sources.status`

- `active`
- `archived`
- `deleted`

### `segments.status`

- `ready`
- `learned`
- `archived`
- `deleted`

### `sessions.status`

- `active`
- `completed`
- `abandoned`

### `review_items.status`

- `active`
- `paused`
- `ignored`
- `deleted`
- `mastered`

## Material boundaries

Do not mix material handling rules across types.

- `subtitle_transcript`
  - clean subtitle artifacts
  - segment by scene or interaction unit
- `spoken_transcript`
  - preserve spoken flow
  - segment by topic and interaction unit
- `article`
  - preserve paragraph and argument structure
  - segment by argument unit

## Session start behavior

When `learning_root` exists, the agent should:

1. read `config.json`
2. read `learner_profile.json`
3. query `sessions` for last activity
4. query `review_items` for overdue pressure
5. decide whether to:
   - review first
   - continue a prepared segment
   - ingest new material

## Write rules

- JSON writes must go through a safe write script
- SQLite writes must go through a helper script or a single controlled transaction path
- `learner_profile.json` is a snapshot, not the source of truth
- profile rebuilds should derive from `profile_events`, `sessions`, and `review_items`
