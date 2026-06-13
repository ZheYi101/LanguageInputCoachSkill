# Track Guide: `article_reading`

Use this track for:

- essays
- blog posts
- op-eds
- explanatory articles
- continuous reading passages

## Mandatory preprocessing

Before lesson generation:

- normalize paragraph structure
- remove copy noise and broken wraps
- preserve argument structure
- follow `references/segmentation-policy.md` for the final lesson cut

## Teaching goal

Prioritize:

- argument comprehension
- paragraph function
- key vocabulary in context
- summary and paraphrase accuracy

Do not prioritize:

- casual spoken tone
- chat-style chunk imitation
- sentence-by-sentence glossing of the entire article
- arbitrary short slicing that breaks a claim-support chain

## What to extract

Select:

- `3-5` key terms
- `2-4` reusable written expressions

Good targets:

- claim framing
- contrast markers
- cause-and-effect language
- evaluation language
- abstract noun + verb/adjective pairings

Examples:

- `raises the question of`
- `is often framed as`
- `comes at the cost of`
- `plays a central role in`

## Scene Capsule requirements

Must clarify:

- the article's main claim or focus
- where the selected passage sits in the argument
- whether the paragraph is introducing, supporting, qualifying, or concluding
- the author's likely communicative goal

## Comprehension Check design

Good question types:

- What claim is this paragraph making
- What does the contrast marker signal here
- Which sentence carries the author's stance

Bad question types:

- disconnected word definition drills
- surface trivia

## Error-Prone Rewrite priorities

Target these first:

- abstract collocations
- reference cohesion
- connector accuracy
- paraphrase precision
- over-translation from Chinese rhetorical patterns

Typical fragile areas:

- weak noun-verb pairings
- missing concession or contrast markers
- inaccurate restatement of argument strength

## Contextual Output design

Use one substantial written task:

- 80 to 150 word summary
- paraphrase the author's claim in simpler English
- rewrite the paragraph from a different stance while reusing target language

Require reuse of at least `2-3` target terms or expressions.

## Profile Delta focus

Prefer short fields that capture patterns like:

- `Can identify main claim but paraphrase loses precision`
- `Understands vocabulary roughly but collocations are unstable`
- `Needs more practice with written connectors and stance framing`
