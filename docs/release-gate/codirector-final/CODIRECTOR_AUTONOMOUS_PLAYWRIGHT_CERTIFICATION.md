# Co-Director Autonomous Playwright Certification

**Branch:** `feature/ai-guided-setup`  
**Commit SHA (workspace HEAD at cert):** `fa09c99d6395c29461cdec4555055faad116c435`  
**Date:** 2026-08-03  
**Beta URL:** http://127.0.0.1:8760/  
**API health:** http://127.0.0.1:8758/api/health  

Protected human project (never created / never mutated by this cert):

- ID: `77a4b96c-8e3f-4501-897c-51bab99bedb7`
- Name: `Manual Beta Handoff`
- Observed during final run: **absent (404)** before and after — unchanged; cert did not recreate it

Final integrated run artifacts:

- `docs/release-gate/codirector-final/artifacts/autonomous-cert/CODIRECTOR-AUTONOMOUS-CERT-2026-08-03T07-18-40-571Z/`
- Satellite: `docs/release-gate/codirector-final/artifacts/autonomous-cert/CODIRECTOR-AUTONOMOUS-CERT-2026-08-03T07-19-30-434Z/`
- Repair log: `.../CODIRECTOR-AUTONOMOUS-CERT-2026-08-03T07-18-40-571Z/repair-log.json`

## Final verdict

**GREEN — READY FOR MANUAL CREATOR TESTING**

## Deliverables

| Item | Path |
|---|---|
| Helpers | `tests/e2e/codirector/helpers/autonomousCert.ts` |
| Suite | `tests/e2e/codirector/codirector-autonomous-certification.spec.ts` |
| Artifacts | `docs/release-gate/codirector-final/artifacts/autonomous-cert/<RUN_ID>/` |
| This report | `docs/release-gate/codirector-final/CODIRECTOR_AUTONOMOUS_PLAYWRIGHT_CERTIFICATION.md` |

## Disposable projects (final green run)

| Role | Project ID | Cleanup |
|---|---|---|
| Main Meridian journey | `f4554166-7ae9-4958-bf52-5ae379181d09` | Deleted → 404 |
| Isolation probe | `62e47ffe-2b7a-4001-b42e-e344979c38d9` | Deleted → 404 |
| Library/STT satellite | `68937758-7515-4db2-8918-5e590789cf82` | Deleted → 404 |

Post-run API scan: `CODIRECTOR-CERT*` residue count = **0**.

## Scenario matrix

| Gate | Result | Notes |
|---|---|---|
| Home UI create (`CODIRECTOR-CERT-<ts>`, Series / Web Series) | PASS | Exactly one `POST /api/projects` |
| Co-Director open (normal UI/route) | PASS | |
| Intro Project Meridian | PASS | Acknowledges Meridian / web series / Season 1 |
| Next-step recommendation | PASS | Specific recommendation; question not Wiki canon |
| Lore invite (“Let me explain the signal first”) | PASS | Invite continuation; no questionnaire |
| Signal lore assimilation (47 / mathematical) | PASS | Reply + Wiki |
| Mara character + correction supersession | PASS | Mission lead confirmed going forward |
| Unresolved private facility | PASS | Not forced confirmed |
| Reject hostile signal / unknown intent | PASS | Intent unknown preserved |
| Short “Yes, begin with the main character” | PASS | Character stage focus |
| Episode 1 next three steps | PASS | Sequenced recommendation |
| Draft plan action | PASS | Creator-readable plan draft; active plan `d6141a65-0c3a-43eb-bf93-46f03c47991b` title `Core Foundation & Ep 1 Blueprint` (draft) |
| Image attachment honesty | PASS | Reference-only; vision unavailable disclosed; no path leaks |
| Library modal (All default + Escape) | PASS | Embedded in journey |
| Library filters (Images/Video/Audio) | PASS | Satellite |
| Mic/STT mocked path | PASS | Transcript editable; no auto-send |
| Reload persistence | PASS | Correction + plan request messages survive |
| Project isolation | PASS | Fresh project Wiki empty of Meridian lore |
| Failure injection (`/api/e2e/*`) | SKIP (env) | Beta returns 404 — recorded, not faked green |
| Cleanup + handoff unchanged | PASS | Handoff missing→missing; disposables 404 |

## Failures + repairs + cycle counts

Bounded loop: max 3 repairs / root cause, max 5 integrated reruns.

| # | Root cause | Cycles used | Outcome |
|---|---|---|---|
| 1 | Home create Playwright strict-mode `.or()` | 1 | Helper fixed |
| 2 | Lore assimilation / next-step / rejection / begin-with routing | 1 | Conversation-core product repair |
| 3 | Draft plan swallowed by Characters stage | 1 | `execute_action` / draft_plan path |
| 4 | Satellite grid testid + plan summary assert | 1 | Spec aligned to real UI/API |
| 5 | Attachment honesty + Meridian title extract | 1 | Composer polish |

Full detail: `repair-log.json` in the final run folder.

## Focused vs integrated evidence

| Check | Command / suite | Result |
|---|---|---|
| Conversation core unit | `python -m pytest tests/test_codirector_conversation_core.py -q` (from `studio-api`) | **17 passed** |
| Autonomous cert (integrated + satellite) | `ADEPT_BETA_TARGET=1 npx playwright test tests/e2e/codirector/codirector-autonomous-certification.spec.ts --retries=0` | **2 passed** (43.2s + 16.6s) |
| Beta restart | `Restart-AdeptUI-Beta.ps1` | READY at http://127.0.0.1:8760/ |

Library / mic / media honesty were exercised inside the autonomous suite (journey + satellite) rather than as separate full-suite re-runs after the final polish.

## Wiki / plan / attachment notes

- Wiki assimilation verified via API polls for Meridian / probe / 47 / mathematical / Mara / mission lead during the journey.
- Active plan after draft request: `planId=d6141a65-0c3a-43eb-bf93-46f03c47991b`, state `draft`.
- Attachment: creator-safe reference reply; no absolute filesystem paths in UI or conversation JSON.
- Persisted conversation messages on final green main project before cleanup: **25**.

## Latency notes

- Final Meridian journey wall time ≈ **43.2s**
- Final library/STT satellite ≈ **16.6s**
- Full suite ≈ **1.0m** after Beta already warm

## Cleanup + handoff before/after

| Check | Before | After |
|---|---|---|
| Manual Beta Handoff | missing (404) | missing (404) — equal |
| Disposable project IDs | created during run | all 404 |
| `CODIRECTOR-CERT*` list scan | — | 0 remaining |

## Limitations (honest)

1. **Failure-injection gate environment-limited on live Beta** — `/api/e2e/status` → 404; soft-skipped with artifact `failure-injection.json`. Do not treat as proven failure-path coverage on Beta.
2. **Manual Beta Handoff was already absent** on this Beta instance; cert is 404-tolerant and did not recreate it. Creators using a present handoff project were not regression-tested against a populated handoff corpus in this run.
3. **Draft-plan creation may still involve provider/intelligence tooling** for rich outlines; conversation-core now refuses to swallow the request into character Q&A and returns creator-readable plan/approval language when it handles the turn.
4. Product repairs from this loop are present in the working tree and loaded by the restarted Beta process; they may not yet be committed as a separate SHA beyond `fa09c99…` HEAD.

## Manual creator review path

1. Open http://127.0.0.1:8760/
2. Create a disposable Series → Web Series project (or reuse a safe sandbox — not Manual Beta Handoff).
3. Open Co-Director and walk Project Meridian style beats: intro → next step → lore → Mara → correction → unresolved → reject hostility → character focus → Episode 1 steps → draft plan → attach image → Library → mic if desired.
4. Reload and confirm messages / wiki direction persist.
5. Delete the disposable project when finished.

## Exact final verdict line

GREEN — READY FOR MANUAL CREATOR TESTING
