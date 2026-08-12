# Phase 5 — Script Writer + Wiki Integration

## Script Writer Backend (`app/scriptwriter/`)
- 28 REST routes under `/projects/{id}/scriptwriter`
- Fountain import/export, PDF export, revisions, undo transactions
- Proposal-gated Co-Director tools (9 read + 7 mutating)

## Wiki Integration
- **navEntries.ts**: Added `"scriptwriter"` to ContentTab type + Story group children
- **CoDirectorShell.tsx**: `normalizeContentTab` passes `"scriptwriter"` through
- **CoDirectorProjectContent.tsx**: D1-D5 dropdown fixes (position:fixed menus, outside-click/Escape close)
- **CoDirectorSession.tsx**: `uiAction === "open_scriptwriter"` branch added

## Verified Operator Navigation
- `workspace.open_scriptwriter` tool (handler, registry, OPERATOR_TOOLS, definitions)
- `_NAVIGATE_TARGET_TO_TOOL` maps `script_writer → workspace.open_scriptwriter`

## Frontend 4 Development Cards (Knowledge Cards opening)
- Empty projects show: Talk about the Story, Talk about a Character, Talk about Vision, Talk about Style
- Set conversationGoal + starter message
- Replace production-forward defaults ("Build a scene", "Write a video prompt")

## Certification: GO
