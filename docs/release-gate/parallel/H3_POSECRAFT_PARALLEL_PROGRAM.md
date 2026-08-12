# H3 + PoseCraft Parallel Program Status

**Date:** 2026-08-03  
**Baseline:** `fa09c99d6395c29461cdec4555055faad116c435`  
**Safety gate:** [`PARALLEL_SAFETY_GATE.md`](PARALLEL_SAFETY_GATE.md)  
**Unified implementation report:** [`MINIMAX_H3_AND_POSECRAFT_UNIFIED_IMPLEMENTATION_REPORT.md`](MINIMAX_H3_AND_POSECRAFT_UNIFIED_IMPLEMENTATION_REPORT.md)  
**Canada license clearance report:** [`../minimax-h3/H3_CANADA_LICENSE_CLEARANCE_UNIFIED_REPORT.md`](../minimax-h3/H3_CANADA_LICENSE_CLEARANCE_UNIFIED_REPORT.md)  
**Authoritative MiniMax status (supersedes H3 runtime rows below):** [`../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md`](../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md)

## Worktrees

| Track | Branch | Path | Status |
|---|---|---|---|
| Co-Director Foundation (primary) | `feature/ai-guided-setup` | `C:\AdeptFilmWorks\AIVideoStudio` | Continues separately |
| MiniMax H3 | `spike/minimax-h3-rtx5090` (earlier Canada docs: `spike/minimax-h3-33b-rtx5090`) | `C:\AdeptFilmWorks\AIVideoStudio-h3` | See unified MiniMax report — Route A PRIMARY ACCEPTED with limitations; Creator Disabled |
| PoseCraft v1.1 | `feature/posecraft-v1-1-foundation` | `C:\AdeptFilmWorks\AIVideoStudio-posecraft` | Handoff complete |

## Track A — MiniMax H3

> **Supersession:** For current H3 local-runtime and program status, use [`../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md`](../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md). The Canada Diffusers spike verdict below remains historical evidence of that failed approach only.

- **HEAD:** `c932214` (territory-gate fix + corrected verdict; Route A run `RUN-20260803-181526`)
- **License verdict:** `CANADIAN LOCAL DEVELOPMENT PERMITTED WITH CONDITIONS`
- **Historical Canada Diffusers / shard spike:** Gate A passed; Gate B FAIL / Gate C NO-GO → `CANADA RUNTIME NOT PROVEN — H3 REMAINS NO-GO` (closed; not current Route A status)
- **Current local runtime (Route A, PRIMARY ACCEPTED):** `ROUTE A PROVEN WITH LIMITATIONS — INTEGRATION MAY PROCEED` — genuine T2VA on isolated `:8192`; Creator H3 remains Disabled
- **Contracts:** drafted under spike `docs/models/minimax-h3/`; experimental stubs unregistered in production
- **Reviewer:** territory gate hardened; Route A primary-accepted separately
- **Historical handoff string (superseded for runtime):** `CANADA RUNTIME NOT PROVEN — H3 REMAINS NO-GO`
- **Handoff:** `AIVideoStudio-h3/docs/models/minimax-h3/H3_PARALLEL_SPIKE_HANDOFF.md` (updated for Route A)
- **Primary accepted disposition:** see unified MiniMax report

### H3 next-step checklist (post–Route A)

1. Deliberate Adept UI Runtime Adapter integration (feature-flagged; Creator Disabled until cert).  
2. Keep LTX as the permanent explicit fallback.  
3. Trained-range quality proof and/or cu130 kernel path before creator-facing toggle.  
4. Law #28 Co-Director disposable-project Playwright certification before any Creator enablement.  
5. Retain Diffusers FL2VA for Route B only; do not force shards into Comfy Route A.

## Track B — PoseCraft

- **Foundation HEAD:** `719896280782434b49aa80594290900413886932`
- **Current HEAD:** `2e4246f54aee8fe76bd81ba771b5b2fe579f3fa6` (independent reviewer pass committed)
- **Route:** `/posecraft-lab` (isolated; not production-wired)
- **Delivered:** Babylon stage, 4 procedural archetypes, posing, presets, camera/lenses/guides, local save/load/undo, exports, draft contracts
- **Tests:** vitest `5 passed`; Playwright foundation spec `1 passed` (standalone Vite)
- **Limitations:** no Co-Director/registry/DB wiring; full `studio-web` build still blocked by unrelated Voice Studio TS errors in this worktree baseline; lazy-load / schema-control / a11y risks noted by reviewer
- **Handoff verdict:** `READY WITH LIMITATIONS` (reviewer agrees — do not upgrade)
- **Handoff:** `AIVideoStudio-posecraft/docs/posecraft/POSECRAFT_V1_1_PARALLEL_FOUNDATION_HANDOFF.md`
- **Reviewer:** `AIVideoStudio-posecraft/docs/posecraft/POSECRAFT_REVIEWER_PASS.md` → `READY FOR PRIMARY REVIEW`

## Merge policy

Do **not** auto-merge. Intended order after Co-Director Foundation green:

1. Review/merge H3 findings (docs + experimental namespace only)
2. Keep Canadian local clearance documented and maintain excluded-territory blocking before any local H3 weight runtime
3. Certify H3 E2E only after runtime proof; preserve LTX fallback
4. Independent review, then merge PoseCraft foundation (`/posecraft-lab` first)
5. PoseCraft project persistence + shared routing
6. Wire PoseCraft → Co-Director / Image Studio
7. Wire PoseCraft refs → H3 / LTX when H3 local becomes lawful and actually proven on GPU
8. Cross-feature Playwright

## Program verdict

**PARALLEL PROGRAM COMPLETE — BOTH TRACKS READY**

Meaning: both isolated handoff packages are complete and ready for deliberate integration review — not production-integrated.

- H3: see [`../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md`](../minimax-h3/H3_UNIFIED_MILESTONE_REPORT.md) — Route A local media proven with limitations; Creator production remains Disabled; Canada Diffusers spike remains historical NO-GO only.
- PoseCraft: product foundation mergeable with disclosed limitations (`READY WITH LIMITATIONS`); independent reviewer pass complete at `2e4246f` — primary merge decision still required before shared integration.
