# Subtitle Ingestion

Use this reference when the user wants repeatable subtitle cleaning or wants local subtitle files imported into a persistent `learning_root`.

This reference assumes the subtitle material is already available locally.
Do not turn this workflow into a browser-login or cookie-handling retrieval flow.

## When to use

Load this reference when any of these are true:

- the source is a local `.srt` file
- the source is a local `.vtt` file
- the source is a local `.ass` or `.ssa` file
- the user wants to clean many subtitle files in one folder
- the user wants ordered batch import from a manifest
- the user wants cleaned text, stored segments, and DB registration before building lessons

Do not use this reference when the real task is:

- downloading subtitles from a protected platform
- using account cookies to reach gated subtitle tracks
- browser automation for acquisition rather than local file processing

## Scripts

Prefer these bundled scripts:

- `scripts/normalize-subtitle-transcript.py`
- `scripts/render-lesson-ready-transcript.py`
- `scripts/clean-subtitle-transcript.py`
- `scripts/ingest-subtitle-into-learning-root.py`
- `scripts/test-subtitle-pipeline.py`

## Track choice

Choose `track` from communicative shape after cleaning:

- `live_chat`
  - livestreams
  - conversational transcripts
  - casual interaction-heavy material
- `article_reading`
  - documentary narration
  - historical explanation
  - essay-like exposition inside subtitle files

Do not decide the track from `.srt` or `.vtt` alone.
Do not decide the track from `.ass/.ssa` alone either.

## Preferred staged workflow

When the goal is reliability and low token usage, prefer a staged pipeline:

1. normalize the raw subtitle file into a structured intermediate artifact
2. render lesson-ready Markdown from that normalized artifact
3. optionally import the result into `learning_root`

This keeps the first pass mechanical and format-driven before any later lesson-building work.

## Normalization workflow

For one-off normalization:

```powershell
python scripts/normalize-subtitle-transcript.py path\to\file.vtt
```

For a whole directory:

```powershell
python scripts/normalize-subtitle-transcript.py path\to\folder
```

For an ordered batch:

```powershell
python scripts/normalize-subtitle-transcript.py --manifest path\to\order.txt
```

The normalizer should:

- support `.srt`, `.vtt`, and basic text-focused `.ass/.ssa`
- strip subtitle timing and markup
- remove rolling-caption overlap from raw `.vtt`
- strip ASS/SSA override tags and dialogue formatting artifacts
- emit `.normalized-subtitle.json`

## Render workflow

After normalization, render lesson-ready output with an explicit track:

```powershell
python scripts/render-lesson-ready-transcript.py --track article_reading path\to\file.normalized-subtitle.json
```

For a folder of normalized files:

```powershell
python scripts/render-lesson-ready-transcript.py --track article_reading path\to\normalized-folder
```

The renderer should:

- require explicit `--track`
- emit `.lesson-ready.en.md`
- emit `.lesson-ready.en.txt` only when explicitly requested with `--emit-txt`

## Combined cleaning workflow

Use the combined cleaner only when a one-command shortcut is more useful than an observable staged pipeline.

For one-off cleaning without DB import:

```powershell
python scripts/clean-subtitle-transcript.py --track article_reading path\to\file.vtt
```

For a whole directory:

```powershell
python scripts/clean-subtitle-transcript.py --track article_reading path\to\folder
```

For an ordered batch:

```powershell
python scripts/clean-subtitle-transcript.py --track article_reading --manifest path\to\order.txt
```

The cleaner should:

- support `.srt`, `.vtt`, and basic text-focused `.ass/.ssa`
- strip subtitle timing and markup
- remove rolling-caption overlap from raw `.vtt`
- emit `.lesson-ready.en.md`
- emit `.lesson-ready.en.txt` only when explicitly requested with `--emit-txt`
- internally be treated as a shortcut over the staged normalization and render flow

## Persistent import workflow

For import into a `learning_root`:

```powershell
python scripts/ingest-subtitle-into-learning-root.py --learning-root path\to\root --track article_reading path\to\file.vtt
```

Or import from a normalized artifact:

```powershell
python scripts/ingest-subtitle-into-learning-root.py --learning-root path\to\root --track article_reading path\to\file.normalized-subtitle.json
```

For a directory:

```powershell
python scripts/ingest-subtitle-into-learning-root.py --learning-root path\to\root --track article_reading path\to\folder
```

For an ordered manifest:

```powershell
python scripts/ingest-subtitle-into-learning-root.py --learning-root path\to\root --track article_reading --manifest path\to\order.txt
```

The importer should:

- copy raw subtitle files into `languages/en/raw`
- write cleaned Markdown artifacts into `languages/en/cleaned`
- write cleaned plain-text artifacts only when explicitly requested with `--emit-txt`
- create segment files in `languages/en/segments`
- upsert `sources` rows
- replace segment rows for that source
- update `learner_profile.json`
- accept either raw subtitle files or normalized subtitle artifacts

## Test fixtures

Use the bundled test script when changing subtitle parsing or cleaning rules:

```powershell
python scripts/test-subtitle-pipeline.py
```

The current fixture set covers:

- basic `.srt`
- rolling `.vtt`
- multiline `.vtt`
- basic `.ass`

## Manifest guidance

Use a plain text manifest when:

- the folder order is not the learning order
- the user wants only selected episodes
- the user has already watched a subset in sequence

One path per line.
Allow absolute paths or paths relative to the manifest file.

## Segment expectations

For imported subtitle material:

- keep segment sizes teachable
- preserve real context
- store `context_before_summary` and `context_after_summary`
- avoid slicing documentary narration into disconnected trivia chunks

## Validation checklist

After cleaning or import, quickly verify:

- the cleaned text is readable as continuous text
- repeated rolling-caption prefixes are gone
- the chosen `track` matches the cleaned communicative form
- the segment summaries are grounded enough for later lesson selection
- the stored paths and DB rows point to the new artifacts
