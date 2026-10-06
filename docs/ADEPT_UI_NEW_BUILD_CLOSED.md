# Adept UI — New Build Closed / Final Convergence Law

**Canon.** Law 30: this is the only governing document for New Build Closed.  
**Number:** Law 33 (Owner draft said “Law 31”; Law 31 remains Evidence Before Completion; Law 32 remains Co-Director Intelligence).  
**Date:** 2026-09-21.

Unlock phrase only:

`Owner unlock: New Build — <named capability>`

---

NEW BUILD CLOSED: Assume the required capability already exists. Audit and reconnect the existing implementation end-to-end, remove any dual-stack contamination, repair every in-scope defect through a continuous GO loop, then lock the certified system. Do not create a replacement or new subsystem without explicit Owner authorization.

**Posture:** BUILD CLOSED — CONVERGENCE OPEN.

The default assumption is: everything Adept UI needs has already been built. When something is missing, broken, disconnected, partially functional, inaccessible, inconsistent, duplicated, or disabled, the first assumption is not “we need to build something new.” It is: the existing system is present but disconnected, contaminated, stale, partially migrated, incorrectly gated, or not wired end-to-end.

---

## 1. New Build Closed

NEW BUILD = CLOSED.

No agent may independently:

- create a replacement subsystem
- create a new architecture
- add another orchestration layer, state store, or compatibility layer
- create an alternate workflow because the current one is hard to repair
- duplicate an existing capability or introduce a second implementation
- rebuild a functioning UI/system from scratch
- create temporary shims that become permanent
- bypass a broken existing path by creating a new path

unless the Owner writes the unlock phrase above (or equivalent explicit authorization).

## 2. Restore Before Build

For every defect, investigate first:

EXISTS? → DISCONNECTED? → PARTIALLY WIRED? → STALE? → DUAL STACK? → WRONG AUTHORITY? → GATED? → DEAD CALLER? → BROKEN CONTRACT?

Priority:

RESTORE → RECONNECT → RETARGET → REMOVE CONFLICT → VERIFY

not REBUILD.

## 3. Existing Capability Is Presumed Intentional

If Adept UI already has the button, panel, route, workflow, adapter, generator, Timeline/creator/Library/Co-Director path, render/continuity/voice/publish/reference/project function, assume it was built on purpose. Find why it is not end-to-end. Do not remove or replace it because the wiring is incomplete.

## 4. Full End-to-End Audit

USER ACTION → FRONTEND → STATE / STORE → API → BACKEND → PROVIDER / RUNTIME → RESULT → PERSISTENCE → UI REFRESH → RELOAD → DOWNSTREAM CONSUMERS

Code exists, unit tests pass, 200, button renders, or backend “success” is not GO. GO requires the creator-facing journey.

## 5. No Partially Working Systems

“Mostly works,” backend-only, UI-only, fails reload, one asset type, API-only, Co-Director-only, first-window-only, except references/audio/global assets — all **NO-GO** until repaired.

## 6. Dual Stack Contamination

Old store + new store, old API + new API, legacy UI + canonical backend, old IDs + canonical IDs, shadow persist, compatibility projection as authority, duplicate references/routes/adapters.

IDENTIFY CANONICAL AUTHORITY → MIGRATE NECESSARY DATA → RETARGET LIVE CALLERS → REMOVE LEGACY AUTHORITY → REMOVE DUAL WRITE/READ → REMOVE SHADOW VERIFY → RETEST E2E

No permanent sync layer. No ongoing bidirectional old ↔ new. One live authority.

## 7. System-State Authority

SYSTEM STATE > VERIFIED TOOL RESULT > CONVERSATIONAL MEMORY

READ → ACT → READ → VERIFY → REPORT. Never remembered success.

## 8. Continuous GO Loop

FIND → TRACE → CLASSIFY → REPAIR → TEST → LIVE VERIFY → RELOAD → DOWNSTREAM VERIFY → SECOND AUDIT

Then repeat. Intermediate labels (IMPLEMENTED, PARTIAL GO, READY FOR REVIEW, MOSTLY WORKING, ONE FAILURE REMAINS) are not the end.

Ends only at:

`GO — <SYSTEM> FULLY VERIFIED`

or

`NO-GO — GENUINE EXTERNAL BLOCKER`

A repairable defect is not an external blocker.

## 9–10. Binary GO means end-to-end

Every existing system must eventually receive binary GO. GO requires UI, API, persistence, runtime, result, reload, downstream — and where applicable real browser, asset, model, provider, job, output. No mocks for final certification.

## 11–12. Lock after GO

GO → LOCK in `docs/ADEPT_UI_COMPLETED_SYSTEM_LOCK.md`. A new defect does not unlock a locked module. Unlock is Owner-only. First ask whether the defect is the caller, boundary, handoff, consumer, or config.

While locked: INSPECT / TEST / REPORT. Not MODIFY / REFACTOR / REPLACE.

## 13. No Convenience Architecture

No new store, manager, registry, router family, compatibility service, orchestration layer, event bus, or asset/provider/timeline abstraction without Owner authorization. Reuse and reconnect.

## 14. No Silent Fallback

No silent switch of model, asset, character, provider, legacy state, placeholder, generic reference, other project, or default config unless Owner-approved designed behavior. Otherwise fail honestly and repair the real path.

## 15. Reference and Identity Integrity

Do not build an alternate identity/reference system. Repair:

canonical asset → canonical tag → Master binding → compile → model input → output identity

No substitutions, silent drops, or alias proliferation.

## 16. Historical Code Is Not Product Authority

Legacy may remain only when classified MIGRATION / TEST / ARCHIVE / DEAD / COMMENT / TOMBSTONE. It must not be reachable from product execution. Unexplained runtime dependency on legacy architecture is **NO-GO**.

## 17–19. Final Convergence

Walk one system at a time: map → canonical authority → UI→runtime→result → dual stack → dead wiring → stale compatibility → repair existing only → live/reload/downstream → second audit → binary GO → lock → next.

Named defects are the starting set. In-scope discoveries join the same mission. No new features during convergence unless existing capability cannot satisfy the request. Only the Owner reopens feature development.

## 20. Permanent loop

AUDIT → RECONNECT → REMOVE DUAL STACK → VERIFY E2E → REPAIR → REVERIFY → GO → LOCK
