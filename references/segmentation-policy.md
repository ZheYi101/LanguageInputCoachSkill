# Segmentation Policy

Use this reference after cleaning and before lesson generation.

## Default strategy

The default is `medium segmentation`.

That means:

- cut material into teachable units
- preserve real context
- avoid giant sessions
- avoid fragmenting the source into tiny decontextualized pieces

## Hard rule

Do not apply one segmentation logic to all material types.

## `subtitle_transcript`

Examples:

- livestream subtitle files
- VTuber recordings
- YouTube spoken subtitles

Segment by:

- scene change
- interaction goal
- topic shift
- tone shift

Preserve:

- enough lead-in to understand the joke, tension, or instruction
- enough tail context to see how the scene resolves

Do not:

- split every few lines
- cut a control/joke/setup/payoff sequence into separate lessons
- optimize only for short lesson length

## `spoken_transcript`

Examples:

- manually cleaned spoken transcripts
- podcast or monologue transcripts

Segment by:

- coherent topic block
- stable speaker intention
- manageable lesson scope

Do not:

- merge unrelated tangents into one lesson
- force written-style paragraph logic onto spoken content

## `article`

Examples:

- essays
- opinion pieces
- explanatory articles

Segment by:

- argument unit
- paragraph cluster
- claim/support/qualification boundary

Preserve:

- claim and support in the same lesson when they depend on each other
- contrast and concession markers with enough surrounding text

Do not:

- split a single argument chain into arbitrary short pieces
- cut out one paragraph if it depends heavily on the previous one

## Segment metadata

Every stored segment should keep:

- `start_ref`
- `end_ref`
- `scene_or_argument_summary`
- `context_before_summary`
- `context_after_summary`

This allows later review and lesson generation to stay grounded without reopening the full source every time.

## User-facing rule

If the source is very long, say clearly:

- that you cleaned it first
- that you selected one representative segment
- why that segment is a good first lesson unit
