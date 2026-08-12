# Wiki Specialist Roster Audit

**Date:** 2026-08-06  
**Source:** live `SpecialistRegistry` + `specialist_policies.py` + `prompts/specialists/`  
**Creator-facing allowed:** never (`creatorFacingAllowed=false` for all)

## Summary

| Metric | Count |
|--------|------:|
| Enabled prompt specialists | 38 |
| Wiki-write curated set | curated via `WIKI_WRITE_SPECIALIST_IDS` |
| Missing required roles | 0 (all 6 implemented) |
| Unsupported wishlist (non-blocking) | 2 |

## Existing specialists

| ID | Name | Priority | Wiki domains | Verdict |
|----|------|---------:|--------------|---------|
| director | Director | 90 | story, visual | ACTIVE_AND_CERTIFIED |
| story-analyst | Story Analyst | 88 | story | ACTIVE_AND_CERTIFIED |
| bible-manager | Production Bible Manager | 86 | canon, world | ACTIVE_AND_CERTIFIED |
| producer | Producer | 85 | production, assets | ACTIVE_AND_CERTIFIED |
| pipeline-manager | Pipeline Manager | 84 | production, assets | ACTIVE_AND_CERTIFIED |
| code-director | Code Director | 83 | production | UNUSED (not Wiki department) |
| technical-director | Technical Director | 82 | production | UNUSED (not Wiki department) |
| screenwriter | Screenwriter | 80 | story | ACTIVE_AND_CERTIFIED |
| continuity-analyst | Continuity Analyst | 78 | timeline, canon | ACTIVE_AND_CERTIFIED |
| prompt-architect | Prompt Architect | 76 | visual | ACTIVE_AND_CERTIFIED |
| story-editor | Story Editor | 75 | story, characters | ACTIVE_AND_CERTIFIED |
| script-supervisor | Script Supervisor | 74 | timeline, wardrobe, props | ACTIVE_AND_CERTIFIED |
| art-director | Art Director | 72 | visual, locations | ACTIVE_AND_CERTIFIED |
| cinematographer | Cinematographer | 70 | visual | ACTIVE_AND_CERTIFIED |
| production-designer | Production Designer | 68 | locations, world, props | ACTIVE_AND_CERTIFIED |
| performance-director | Performance Director | 66 | characters, audio | ACTIVE_AND_CERTIFIED |
| choreographer | Choreographer | 65 | story | UNUSED (optional Wiki) |
| editor | Editor | 64 | story, timeline | ACTIVE_AND_CERTIFIED |
| qa-reviewer | QA Reviewer | 63 | canon | ACTIVE_AND_CERTIFIED |
| vision-reviewer | Vision Reviewer | 62 | visual | ACTIVE_AND_CERTIFIED |
| asset-manager | Asset Manager | 61 | assets, references | ACTIVE_AND_CERTIFIED |
| casting-director | Casting Director | 60 | characters | ACTIVE_AND_CERTIFIED |
| lighting-supervisor | Lighting Supervisor | 59 | visual | ACTIVE_AND_CERTIFIED |
| vfx-supervisor | VFX Supervisor | 58 | visual | ACTIVE_AND_CERTIFIED |
| animation-supervisor | Animation Supervisor | 57 | visual | UNUSED (optional Wiki) |
| compositing-supervisor | Compositing Supervisor | 56 | visual | UNUSED (optional Wiki) |
| character-creator | Character Creator | 55 | characters, wardrobe | ACTIVE_AND_CERTIFIED |
| sound-designer | Sound Designer | 55 | audio, locations | ACTIVE_AND_CERTIFIED |
| virtual-production-coordinator | Virtual Production Coordinator | 52 | production | UNUSED (optional Wiki) |
| music-supervisor | Music Supervisor | 50 | audio | ACTIVE_AND_CERTIFIED |
| sound-producer | Sound Producer | 48 | audio | ACTIVE_AND_CERTIFIED |
| storyteller | Storyteller | 40 | story | ACTIVE_AND_CERTIFIED |

## Newly implemented Wiki department roles

| ID | Role | Verdict |
|----|------|---------|
| costume-designer | Costume Designer | ACTIVE_AND_CERTIFIED |
| props-master | Props Master | ACTIVE_AND_CERTIFIED |
| storyboard-artist | Storyboard Artist | ACTIVE_AND_CERTIFIED |
| worldbuilding-specialist | Worldbuilding Specialist | ACTIVE_AND_CERTIFIED |
| research-specialist | Research Specialist | ACTIVE_AND_CERTIFIED |
| marketing-pitch | Pitch / Marketing Producer | ACTIVE_AND_CERTIFIED (scope-limited) |

## Unsupported (documented, not fake-GO)

| ID | Note |
|----|------|
| treatment-writer | Covered partially by screenwriter/story-editor |
| dialogue-specialist | Covered partially by screenwriter |
| comparables-analyst | Absent; not required for Wiki reorganization |
| distribution-festival-youtube | Absent; marketing-pitch covers pitch only |

## Policy

- `mayProposeWikiWrites=true` only for curated Wiki-department IDs (`WIKI_WRITE_SPECIALIST_IDS`)
- `creatorFacingAllowed=false` for all
- `mayExecuteTools=false` for all
- Orchestrator owns apply; specialists return structured findings only
- Assignment is problem-driven (max ~8 specialists); never all-specialists-every-message

## Contracts frozen

- `WikiSpecialistFinding`
- `WikiSpecialistAssignment`
- `WikiIntelligenceDecision`
- `WikiReorganizationJob` / `WikiReorganizationRevision` / `WikiChangeRecord`
- `WikiOrganizationProblem`
- Projection DTOs assembled from Bible + Character Identity + knowledgeEntries bridge
