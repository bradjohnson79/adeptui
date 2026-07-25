# Co-Director Production Intelligence (M2.4)

Co-Director M2.4 adds a unified production intelligence layer behind the existing chat gateway. The user speaks to one partner; internally Co-Director classifies intent, compiles Production Bible context, selects a bounded specialist team, synthesizes findings, builds auditable production plans, and creates M2.2 proposals for mutating work.

## Guiding principle

Prompts provide production experience. Code provides discipline. The Production Bible provides truth. Co-Director provides one unified voice.

## Feature flag

Enable with `STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2=1` (default off). When disabled, chat follows the M2.2 path unchanged.

## Vertical slice

Create the next storyboard shot exercises Bible context retrieval, specialist selection, synthesis, plan creation, and `propose_storyboard_generation` — visual validation is marked pending for M2.5.
