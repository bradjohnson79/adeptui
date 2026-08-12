# Benchmark Design

## Suites

| Suite | Domain | Matrix |
| --- | --- | --- |
| `video-core` | video | reduced: creator, refined-english, bilingual-balanced |
| `image-core` | image | full 5 strategies |
| `audio-core` | audio | reduced |
| `voice-core` | voice | reduced |

## Case fields

`benchmarkId`, `domain`, `category`, `creatorPrompt`, `negativePrompt`, `continuityContext`, `expectedIntent`, `lockedTerms`, `providerEligibility`, `evaluationCriteria`, `controlSettings`.

## Controls

Seeds, resolution, duration, fps held constant across strategies in a case. Only the prompt strategy changes.
