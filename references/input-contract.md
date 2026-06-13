# Input Contract

This skill starts after the learner already has English text.

## Required fields

- `input_type`
  - Allowed: `transcript`, `article`
- `track`
  - Allowed: `live_chat`, `article_reading`
- `title`
- `text`

## Optional fields

- `learner_language`
  - Default: `zh-CN`
- `source_url`
- `creator_or_channel`
- `watched_or_read`
  - Default: `true`
- `material_type`
  - Suggested: `subtitle_transcript`, `spoken_transcript`, `article`
- `learning_root`
  - Required for persistent workspace mode

## v1 rules

- Do not auto-detect the track.
- If `track` is missing, ask the user to choose.
- If `learning_root` exists, treat the session as persistent workspace mode and read `state-schema.md`.
- If the input is a raw transcript or subtitle dump, normalize it before teaching.
- If `text` is too long for one useful session, select a representative slice from the cleaned text and say so.
- Keep the lesson scoped to what the learner plausibly watched or read.

## Normalization requirement

For `transcript` input, treat normalization as mandatory when the text still contains raw subtitle artifacts such as:

- numeric subtitle indices
- time ranges
- broken line wraps from one sentence
- duplicate lines
- obvious ASR noise or subtitle junk

Do not build a lesson directly from this raw form if it can be cleaned first.

## Suggested normalized input shape

```json
{
  "input_type": "transcript",
  "track": "live_chat",
  "material_type": "subtitle_transcript",
  "title": "Dual-stream opening segment",
  "text": "Cleaned transcript text or a cleaned selected excerpt",
  "learner_language": "zh-CN",
  "source_url": "https://example.com/video",
  "creator_or_channel": "Example Channel",
  "watched_or_read": true,
  "learning_root": "/path/to/learning-root"
}
```

## Follow-up review shape

When the learner answers exercises, they do not need to resend a full JSON object. They only need enough context for the assistant to identify:

- which input passage the lesson came from
- which targets were assigned
- which answers belong to `Comprehension Check`, `Error-Prone Rewrite`, or `Contextual Output`

If prior context is missing, ask for the original lesson or restate the targets before correcting.
