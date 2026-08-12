# Co-Director Foundation Contracts (Frozen)

**Status:** Frozen for Phases 1.5–6 parallel implementation  
**Package:** `studio-api/app/codirector/foundation/contracts.py`

## Standing laws

1. **Conversation Core is the gateway** — do not replace `conversation/`.
2. **One orchestration pipeline** — Domain → Knowledge → Router → Specialists → Creative Director → Synthesis → Approvals/Tools → Memory.
3. **Creator authority** — suggest/analyze/draft/prepare/compare/warn/execute-approved only. No silent canon, silent approve, overwrite without undo, costly generation without approval, autonomous deletion, or direction change without consent.
4. **Truthful actions** — never claim saved/generated/approved/uploaded/scheduled/completed until success.
5. **Project isolation** — no cross-project facts, assets, plans, conversations, preferences, specialist results, caches, or jobs.
6. **Specialist discipline** — specialists return structured analysis only; Synthesis + Conversation Core address the creator.
7. **Shared knowledge only** — craft doctrine lives in the Creative Knowledge Framework; specialists must not embed private copies.
8. **Creative Director before Synthesis** — editor-in-chief review when multi-specialist output is merged.
9. **Playwright disposable-project gate** — no capability is complete until autonomous Playwright passes against a brand-new disposable project.

## Preserve-first mapping

| Mission name | Frozen approach |
|---|---|
| `ConversationPlan` | `conversation.schemas.ConversationPlan` |
| `ProjectIntelligenceSnapshot` | `conversation.schemas.ProjectIntelligenceSnapshot` |
| `CreativeState` | `foundation.contracts.CreativeState` |
| `ProjectDirectorState` | `conversation.schemas.ProjectDirectorState` |
| `KnowledgePack` / `KnowledgeFrame` | `foundation.contracts` (Phase 1.5) |
| `SpecialistRequest` | `foundation.contracts.SpecialistRequest` |
| `SpecialistResult` | extends `SpecialistFinding` |
| `CreativeDirectorReview` | `foundation.contracts.CreativeDirectorReview` |
| `SynthesisResult` | `intelligence.schemas.SynthesisResult` |
| `KnowledgeEntry` / Wiki | conversation wiki lifecycle (project memory ≠ craft packs) |
| `ProductionTask` | alias `ProductionPlanStep` |
| `ProjectBlocker` | alias `ProductionPlanBlocker` |
| `ApprovalRequest` | facade DTO |
| `ActivityEvent` | foundation DTO |
| `ToolReceipt` | foundation DTO |
| `AutonomousWorkflow` | foundation DTO |
| `DomainProfile` | foundation DTO |

## Ownership (non-overlapping)

| Area | Paths |
|---|---|
| Knowledge 1.5 | `foundation/knowledge/**`, `config/codirector/creative-knowledge/**` |
| Creative 2 | `foundation/creative/**` |
| Production 3 | `foundation/production/**` |
| Collaboration 4 | `foundation/collaboration/**` |
| Operations 5 | `foundation/operations/**` |
| Domains 6 | `foundation/domains/**`, `config/codirector/domain-profiles/**` |
| Integration | `intelligence/service.py`, `service.py`, UI chrome — **primary only** |

## Contract change policy

Parallel subagents may not redefine shared schemas. Additive fields require primary approval and an update to this document.
