# Track Guide: `live_chat`

Use this track for:

- VTuber streams
- YouTube or Twitch chatting segments
- Casual conversational subtitles
- Interactive spoken content with rapid topic shifts and strong tone

## Mandatory preprocessing

Before target extraction, first convert raw subtitle text into a lesson-ready passage.

Minimum cleaning steps:

- remove subtitle indices
- remove timestamps
- merge broken lines that belong to one sentence
- drop obvious duplicates
- remove obvious subtitle noise that does not help learning

Then:

- choose a coherent scene-sized segment
- keep enough surrounding context for tone and interaction to remain visible
- follow `references/segmentation-policy.md` for the actual cut

Do not skip straight from raw `.srt` text to chunk extraction unless the text has already been cleaned elsewhere.

Default segmentation posture:

- medium segmentation
- preserve scene-level coherence
- avoid fragmenting setup, control, joke, and payoff into separate micro-lessons

## Teaching goal

Prioritize:

- spoken comprehension
- scene-aware interpretation
- reusable chunks and formulaic phrasing
- contextual spoken output

Do not prioritize:

- exhaustive transcript coverage
- formal grammar sequencing
- long word lists detached from scene and tone
- raw subtitle fidelity at the cost of lesson quality

## What to extract

Select `5-8` items. Prefer:

- high-reuse chunks
- stance markers
- scene-management language
- interpersonal phrases
- natural spoken framing

Examples of good targets:

- `take some getting used to`
- `get along`
- `sort it out`
- `that checks out`
- `sounds about right`

Examples of low-value targets:

- names
- single obvious adjectives with no reuse value
- one-off jokes that do not generalize
- filler with no pragmatic value

## Scene Capsule requirements

Must clarify:

- who is speaking to whom
- what is happening in the scene
- why the speaker says these lines now
- the intended tone, such as teasing, reassuring, stalling, or reacting

Do not write a neutral summary that loses the interaction.

## Comprehension Check design

Good question types:

- What is the speaker trying to make the audience do
- Is this line serious, playful, or half-serious
- What does a chunk mean in this exact moment

Bad question types:

- dictionary-style definition recall with no scene
- trivia about the transcript

## Error-Prone Rewrite priorities

Target these first:

- subject choice
- adjective clause stability
- fixed chunk integrity
- spoken naturalness
- over-literal Chinese-to-English transfer

Typical fragile areas:

- `This setup is overstimulating`, not `This setup makes overstimulating`
- `It's gonna take some getting used to`, not `I'm gonna take some getting used to`
- `You're gonna have to learn to get along`, not partial rewrites that break the chunk

## Contextual Output design

Ask the learner to speak inside the original situation.

Strong prompts:

- Continue the speaker's opening in 4 to 6 lines
- Rephrase the speaker's point while keeping the same tone
- Say what you would say to calm down two chat groups in one room

Weak prompts:

- Make random sentences with the target phrase
- Translate isolated lines with no scene

## Profile Delta focus

Prefer short fields that capture patterns like:

- `Understands scene but weak at stable spoken production`
- `Recognizes chunks but breaks them during output`
- `Needs more practice with adjective predicates and subject choice`
