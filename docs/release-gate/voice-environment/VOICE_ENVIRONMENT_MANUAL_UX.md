# Voice Environment — Manual UX Checklist

## Live Review Targets

- Beta UI: `http://127.0.0.1:8760/`
- Beta API: `http://127.0.0.1:8758/`

## Review Path

1. Open `http://127.0.0.1:8760/`
2. Go to `Production` -> `Creative Studios`
3. Confirm `Voice Studio` appears as a creator-facing destination
4. Open `Voice Studio`
5. Choose a character with an approved Voice Identity and approved Performance take
6. Move through the stage rail and confirm order:
   `Identity -> Performance -> Environment -> Scene Dialogue -> Takes`
7. In `Environment`, confirm the panel shows:
   dry performance preview, current environment pass, creator-friendly tips, and scene controls
8. Run the creator path:
   recommendation -> preview -> render -> approve
9. After approval, verify the handoff actions are visible and usable:
   `Apply to Scene`, `Send to Timeline`, `Prepare Lip Sync`, `Open in Audio Studio`
10. Reload the page and confirm the selected character, approved state, and latest environment context still appear correctly

## Checklist

1. [ ] Production -> Creative Studios -> Voice Studio is visible and easy to find
2. [ ] Standalone Voice Studio opens character cards without exposing raw IDs
3. [ ] `Create New Character` returns cleanly to Voice Studio flow
4. [ ] Entering Voice Studio from another project entry shows the same saved state
5. [ ] Stage order is `Identity -> Performance -> Environment -> Scene Dialogue -> Takes`
6. [ ] Environment help tips are plain-language and readable
7. [ ] Co-Director recommendation is reviewable before it changes creator state
8. [ ] Custom environment text fields accept typing, spaces, paste, and delete cleanly
9. [ ] Preview does not regenerate or overwrite Voice Identity
10. [ ] Approve preserves the dry take timing
11. [ ] `Send to Timeline` completes and keeps dry + processed context available
12. [ ] `Prepare Lip Sync` uses dry timing rather than processed tails
13. [ ] `Open in Audio Studio` opens the audio workspace with environment context
14. [ ] `Apply to Scene` succeeds for the selected scene
15. [ ] Reload preserves visible Voice Studio state without entry mismatch
16. [ ] Layout remains usable at `1366x768` and `1920x1080`

## Notes For Reviewer

- `runtime/status` is expected to report deterministic acoustic readiness, not AI generation readiness.
- If a handoff button fails, capture which action failed and whether the failure happened before or after approval.
