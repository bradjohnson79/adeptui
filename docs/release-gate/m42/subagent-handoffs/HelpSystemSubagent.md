# Subagent Handoff

## Assignment
HelpSystemSubagent — (?) captions fully visible, top layer. Contract: `subagent-assignments/HelpSystemSubagent.md`.

## Scope completed
- Confirmed `HelpTip.tsx` portals bubbles to `document.body` with fixed positioning, viewport clamp, prefer open-to-the-right, `z-index: 10050`.
- CSS updated for `.help-tip-bubble--portal` (no centered absolute clip inside `shell-pane` overflow).

## Files changed
None in this governance pass (shipped earlier in session; verified in-tree).

## APIs consumed
None.

## APIs changed
None.

## Tests run
None.

## Test results
N/A.

## Manual checks
Requires browser hover on Timeline Scenes `(?)` after beta rebuild — scheduled with beta restart todo.

## Evidence
- `studio-web/src/components/HelpTip.tsx`
- `studio-web/src/styles.css` (`.help-tip-bubble--portal`)

## Known issues
None known in code; visual confirm after production build restart.

## Risks
- Very tall tips near bottom flip above; extreme multi-monitor edge cases untested.

## Dependencies still pending
- Beta rebuild to serve latest web bundle.

## Recommended integration checks
Hover Scenes + Advanced + Voice HelpTips in left/right shell panes.

Ready for integration review.
