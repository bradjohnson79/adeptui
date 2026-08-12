# Phase 4 — Story Intelligence Compiler

## Story Evidence Model (`story_intelligence/story_model.py`)
- `StoryEvidenceModel` with 18 fields (protagonist, premise, conflict, stakes, tone, genre, etc.)
- `StoryFact` with provenance per field
- `build_story_evidence` — reads 8 authoritative sources (Script Writer, Bible, Wiki, Character Identity, etc.)

## Instruction/Content Separation (`story_intelligence/sanitize.py`)
- `separate_instruction` — deterministic prefix split
- `is_contamination_free` — 7-type post-compilation validator

## Compilers (`story_intelligence/compilers/`)
- **Logline** (`logline.py`): one sentence, protagonist + conflict, format-aware, ≤300 chars
- **Short Summary** (`short_summary.py`): 20-150 words, prose only, format-aware
- **Long Summary** (`long_summary.py`): 30-400 words, fuller narrative, no padding

## Proposal Integration (`story_intelligence/proposal.py`)
- `create_story_field_proposal` — routes through existing ProposalService
- `route_compiler_output` — skips empty/no-change proposals
- `apply_story_field_approval` — writes approved artifact verbatim (argument pinned)

## Knowledge Cards (`story_intelligence/knowledge_card.py`)
- 4 card types: STORY, CHARACTER, VISION, PROJECT_STYLE
- Lifecycle: DRAFT→EDITING→ADDED/DISMISSED/FAILED
- Add routes to authoritative systems (Character Identity, compiledWiki, snapshot)
- Ephemeral store (session-scoped dict) — NOT a canonical database

## Tests: 43 (Phase 4) + 9 (Knowledge Cards)
## Certification: GO
