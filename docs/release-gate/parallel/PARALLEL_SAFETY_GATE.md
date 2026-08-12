# Parallel Safety Gate — H3 + PoseCraft

**Date:** 2026-08-03  
**Baseline commit:** `fa09c99d6395c29461cdec4555055faad116c435`  
**Primary branch (untouched for parallel edits):** `feature/ai-guided-setup` @ `C:\AdeptFilmWorks\AIVideoStudio`

## Worktrees

| Track | Branch | Path | Owner |
|---|---|---|---|
| Main / Co-Director Foundation | `feature/ai-guided-setup` | `C:\AdeptFilmWorks\AIVideoStudio` | Primary |
| H3 spike | `spike/minimax-h3-33b-rtx5090` | `C:\AdeptFilmWorks\AIVideoStudio-h3` | GPT-5.4 H3 agents |
| PoseCraft foundation | `feature/posecraft-v1-1-foundation` | `C:\AdeptFilmWorks\AIVideoStudio-posecraft` | GPT-5.4 PoseCraft agents |

## Forbidden shared production paths (both parallel tracks)

Neither worktree may modify:

- `studio-api/app/codirector/conversation/**`
- `studio-api/app/codirector/foundation/**`
- `studio-api/app/codirector/service.py`
- shared specialist / tool registries meant for production wiring
- shared project schemas / lifecycle
- job scheduler / model router / Production Dock
- Setup Wizard production implementation
- Timeline / Audio Studio production implementation
- global Library asset schema
- approval / activity-event production contracts
- human Manual Beta Handoff project data

## Allowed

- Inspect shared files
- Docs under track namespaces
- Isolated experimental modules / routes
- Mock adapters and proposed schemas
- Isolated tests and artifacts

## Integration boundary

No shared production merge until Co-Director Foundation contracts are frozen/green, handoff reports reviewed, and primary integrator maps proposals onto frozen architecture.
