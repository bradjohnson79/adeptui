# Character Creator CRS Sheet — Current State Audit

## Architecture Overview

The Character Creator already has a mature implementation with the following components:

| Component | File | Purpose |
|---|---|---|
| CharacterCore | `CharacterCore.tsx` | Main orchestrator — profile, references, plan, candidates, generation, approval |
| CharacterSheetGenerator | `CharacterSheetGenerator.tsx` | Drives 4-view Character Sheet candidate generation with polling |
| CharacterReferenceControl | `CharacterReferenceControl.tsx` | Reference image upload, Library picker, "Use as Character Identity" |
| CharacterGeneratorPanel | `CharacterGeneratorPanel.tsx` | Generator selection (local/API sources, multi-select) |
| CharacterCandidateGrid | `CharacterCandidateGrid.tsx` | Candidate card grid with selection, preview, retry |
| CharacterProfileForm | `CharacterProfileForm.tsx` | Name, render domain, description |
| GenerationProgressBar | `GenerationProgressBar.tsx` | Progress bar during generation |
| characterSheetGenerate | `characterSheetGenerate.ts` | Sheet generation request building |
| characterGeneratorPlan | `characterGeneratorPlan.ts` | Generator plan hydration from preferences |
| types | `types.ts` | CharacterCandidate, GeneratorOption, CharacterProfile types |
| useCharacterProfile | `useCharacterProfile.ts` | Profile/reference data loading |

## What Already Works

### ✅ Character Profile
- Name, render domain, description fields
- Save/load/persistence
- References (hero identity, reference images)

### ✅ Character Reference
- Upload from file
- Add from Library (`CharacterReferenceAssetPicker`)
- Remove reference
- "Use as Character Identity" path
- Multiple reference types (hero_identity, reference_image)

### ✅ Character Sheet Generation
- 4-view Character Sheet candidate generation
- Multi-generator support (local + API sources)
- Progress bar (`GenerationProgressBar`)
- Candidate polling
- Result display (`CharacterCandidateGrid`)

### ✅ Generator Selection
- Generator inventory (local options, API options)
- Generator plan hydration from preferences
- Source selection (local/API toggles)

### ✅ Candidate Management
- Candidate cards with thumbnails
- Selection state
- Retry for failed candidates
- Approval action ("Promote to Production")

## Identified Gaps

### 1. Qwen Default Generator
The generator plan is hydrated from preferences (`hydratePlanFromPreferences`), but there is no explicit "Qwen is the default" logic. The default plan (`DEFAULT_CHARACTER_GENERATOR_PLAN`) likely has localEnabled=true but no specific model preference.

### 2. Simplified Generator UX
The current `CharacterGeneratorPanel` shows a comprehensive generator list. The mission requests a simplified "Character Reference Sheet Generator" with Qwen as default and an expandable "More Generators" section.

### 3. Character Reference Tooltip
The `CharacterReferenceControl` has a "?" help icon but the tooltip copy needs updating to explain single-view vs multi-view uploads and Co-Director assistance.

### 4. Active CRS Sheet Display
The `CharacterCandidateGrid` shows all candidates. There is no dedicated "Active Character Reference Sheet" section that clearly distinguishes the approved sheet from historical candidates.

### 5. Preview Modal
The `CharacterCandidateGrid` has thumbnails but there is no dedicated modal preview for the approved sheet. Clicking a candidate may navigate to a detail view but not a full-screen modal.

### 6. Regenerate Preserves Prior Version
Regeneration creates new candidates but the "previous approved sheet remains" behavior needs verification.

### 7. 2K Output Contract
The existing ERS 2K contract needs to be audited and applied to CRS Sheet output.

### 8. Approval → Internal CRS Sync
The "Promote to Production" action exists but the internal CRS canon update needs verification.

### 9. Universal @Character Registration
After approval, the character should be resolvable via @Character. This needs verification.

### 10. Character Delete Lifecycle
The cascade delete of CRS canon, @Character registration, and Co-Director state needs implementation/verification.

## ERS Reuse Opportunities

The existing ERS (Environment Reference Sheet) implementation provides:
- 2K generation/output contract
- Sheet display card pattern
- Modal preview pattern
- Regenerate action pattern
- Generation state/progress
- Asset persistence
- Approval state
- Provenance tracking

These patterns should be reused for the CRS Sheet rather than building a parallel system.

## Recommended Priority Order

Given the certification-focused nature of this pass, the recommended implementation order is:

1. **Qwen default generator** — simplest change, highest impact
2. **Simplified generator UX** — collapse advanced options under "More Generators"
3. **Character Reference tooltip** — update copy for single-view/multi-view/Co-Director
4. **Active CRS Sheet display** — distinguish approved sheet from candidates
5. **Preview modal** — reuse ERS modal pattern
6. **Regenerate preservation** — verify prior sheet survives
7. **2K output contract** — audit and apply ERS quality standards
8. **Approval → CRS sync** — verify internal canon update
9. **@Character registration** — verify universal resolver
10. **Delete lifecycle** — verify cascade cleanup
