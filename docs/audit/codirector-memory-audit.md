# Co-Director and Project Memory Audit

## Executive conclusion

Co-Director is one partial system—not multi-agent. It has a FAB/side panel, typed registry, heuristic plans, local permissions/audit, Ollama chat, and KB compiler. It lacks a shared context bus, product operating modes, enforceable permission boundaries, undo, and durable Project Memory.

## Classification

| Capability | Class | Finding |
|---|---|---|
| One Co-Director code path | B | Spatial commands remain parallel |
| FAB + side panel | A/B | Working |
| Home gateway | C | Composer only |
| Shared context | D | Props/sessionStorage |
| Typed action registry | B | Broad but schemas/results are weak |
| Confirmation | C | Client-only and policy bug |
| Undo | F | Metadata only |
| Operating modes | F | Missing |
| Learning JSON | C | Memory precursor |
| KB compiler | B | Working; ignores Memory |

## Broken connections

1. `ExecuteContext.navigate` is not provided for project routing.
2. `saveMemorySuggestion` is a stub although learning APIs exist.
3. compile-prompt does not consume approved learning/memory.
4. client structured context is unused by server compiler.
5. selection IDs are not centrally shared.
6. `"never"` policy can still execute after confirmation.
7. Txt2Vid silently writes learning without approval.
8. Home and project mount separate panel instances without shared conversation state.

## Target context

Project, Scene, active workspace, selected Profile/Asset/Script Segment/Storyboard Panel/Director Sequence/Editor Clip in one store consumed by chat, compiler, plans, and actions.

## Operating modes

| Mode | Mutation policy |
|---|---|
| Guide Me | Suggestions only |
| Collaborate | Step approval |
| Build for Me | Approved non-destructive execution |
| Advise Only | No writes |
| Autopilot | Execute approved plan; stop on cost, ambiguity, destruction, manual checkpoint, export |

## Action gaps

Missing or incomplete: profile CRUD/attach, Script Segment CRUD, Storyboard create/generate, Scene Sheet naming, Director Segment, Audio Job, generic Editor timeline/clip actions, preview render, real Memory save. Existing spatial/master-sheet/avatar actions must migrate rather than expand.

## Memory migration

1. Add `memory_items`.
2. Backfill learning items with approved state and source.
3. Rename Learning UI to Project Memory with compatibility alias.
4. Wire suggestions as unapproved until accepted.
5. Inject approved Memory into compile-prompt.
6. Stop silent auto-learning.
7. Keep learning JSON dual-write through Phase 6.

## Permission and undo plan

- Enforce action permission and operating mode in executor.
- `"never"` blocks rather than confirms.
- Replace `window.confirm` with shared dialog.
- Store inverse payload for reversible mutations.
- For generation actions, offer cancellation rather than undo.
- Long-term mutation validation must be server-side.

## Smoke tests

Panel state, gateway actions, each operating mode, blocked destructive action, audit entry, undo, Memory approval/reload/compiler use, Director→Editor actions, project navigation, no multi-agent behavior.

## Files inspected / unchanged

Assistant panel, Co-Director registry/executor/specs, Home/Dashboard, Learning, assistant/KB APIs, learning state and related consumers. No actions or files changed.

