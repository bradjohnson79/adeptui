# M5.4 Final Preflight — Scope Integrity & Execution Readiness

| Field | Value |
| --- | --- |
| Milestone | `M5.4 — Co-Director Project Intelligence` |
| Preflight date (UTC) | `2026-08-02T19:48:00Z` |
| Independent verifier | GPT-5.4 (`2d491281-44cb-49de-ac00-901ef5900921`) — did not author the master |
| Primary | Transferred verifier evidence into this report |
| **Final verdict** | **BLOCKED** |

## Deduplication summary

Merged iterative M5.4 planning (triad, format awareness, creative direction, operations pane, Decision Records, Visual Wiki, Landing, Project History, export) into one authoritative master with:

- one overview  
- one milestone title  
- one phase table (Phases 0–9)  
- one numbered architecture section  
- one execution order  
- one Definition of Done  
- one GO/NO-GO standard  

Superseded duplicate phase IDs (`1b`, `7b`) were collapsed into sequential phases.

## Authoritative master plan path

`docs/release-gate/m54-project-intelligence/M54_MASTER_IMPLEMENTATION_SPEC.md`

### Freeze block (as stamped)

| Field | Value |
| --- | --- |
| Master specification path | `docs/release-gate/m54-project-intelligence/M54_MASTER_IMPLEMENTATION_SPEC.md` |
| Master specification SHA-256 | `ac78f6c62627cc2a7ebf546159cedb858f914ec0456b2323563d26bc65b40a1a` |
| Git branch | `feature/ai-guided-setup` |
| Git SHA | `fa09c99d6395c29461cdec4555055faad116c435` |
| Freeze timestamp (UTC) | `2026-08-02T19:45:49Z` |
| Contract schema version | `m54.contracts.v1` |

**Freeze integrity issue (Block):** Verifier could not reproduce the SHA-256 under the document’s own verification procedure (replace SHA cell with `PENDING_FREEZE_HASH`, re-hash). Primary must re-stamp a reproducible freeze before READY.

## Existing-system reuse matrix

| System | Reuse intent | Verifier status |
| --- | --- | --- |
| Production Bible | Canon owner; sync/promote only | Pass (ownership) / Block (decision entity overlap) |
| Project Library | Media files | Pass |
| Asset graph | Media lineage only | Pass |
| `m211_decision_records` | Decision Records substrate | Pass intent / Block vs Bible `production_decision` |
| Scriptwriter / Voice / Audio | Deep edit destinations | Pass (by design) |
| Plans / Approvals / Jobs | Elevate into Operations Pane | Pass (by design; UI migration required) |
| Prompt Intelligence + provider registries | Extend; live readiness | Pass |
| Storyboard `TimelinePrepProposal` | Must not compete with `TimelinePreparationPayload` | **Block** — dual contract/store unresolved |
| Co-Director right pane | Replace with Landing + Ops tabs | Pass (migration required) |

## Frozen contract inventory

| Contract family | In master | Verifier |
| --- | --- | --- |
| `ProductionDecisionRecord` | Typed | Pass typed / Block vs Bible decisions |
| `ProjectHistoryEvent` | Typed | Pass |
| `ProjectCurrentTask` | Typed | Pass |
| `TimelinePreparationPayload` | Typed | Block vs existing storyboard prep |
| Export snapshot metadata | Versions + checksum required | Pass at design level |
| Performance budgets | Target + blocking | Pass |
| Wiki article / assertion / graph node-edge / format adapter / landing DTO / ops deep-link / creative plan envelopes | Mostly prose | **Block** — incomplete schema freeze |

## Ownership matrix

| Capability | Owner | Status |
| --- | --- | --- |
| Canon | Production Bible | Pass |
| Readable knowledge | Project Wiki | Pass |
| Relationships / chronology | Knowledge Graph | Pass |
| Media files | Project Library | Pass |
| Production rationale | Decision Records via m211 | **Block** — Bible `production_decision` not deconflicted |
| Creative evolution | Project History | Pass |
| Script / Voice / Audio edit | Respective studios | Pass |
| Editorial assembly | Timeline | Pass |
| Provider readiness | Setup / Dock / registries | Pass |
| Co-Director operations | Proposal-gated tools | Pass |

## Authority and proposal-safety audit

Master defines Inspect → Propose → Explain → Preview → Approve → Execute → Verify → Persist → Re-index and forbids silent canon, silent provider switch, silent Timeline placement, unapproved spend, hidden CPU fallback.

Verifier: **Pass** on design-level authority safety.

## Project-isolation audit

Typed new surfaces require `projectId`. Existing Bible, m211, Library, and storyboard timeline-prep are project-scoped.

Verifier: **Pass**.

## Performance budgets

| Surface | Target | Blocking |
| --- | --- | --- |
| Intelligence Landing warm load | ≤1.0s | >3.0s |
| Wiki article warm load | ≤500ms | >2.0s |
| Operations tab switch | ≤400ms | >1.5s |
| Scoped search | ≤750ms | >2.5s |
| Graph neighborhood | ≤750ms | >2.5s |
| Scene-context retrieval | ≤1.0s | >3.0s |
| Prompt-context compile | ≤1.5s | >4.0s |
| Incremental re-index | ≤2.0s | >8.0s |
| Export job acknowledgement | ≤500ms | >2.0s |
| First useful Co-Director response | ≤4.0s | >10.0s |

Verifier: **Pass** (measurable; hard rejects present).

## Format coverage

One core + adapters; no per-format Wiki/graph forks. Verifier: **Pass**.

## Creative-provider grounding

Live registries / Setup / Dock / runtime; Unknown ≠ Ready. Verifier: **Pass**.

## Transferred verifier evidence

Source: [Independent M54 preflight audit](2d491281-44cb-49de-ac00-901ef5900921)

### Evidence

1. **Finding:** Freeze header fields present; branch and git SHA match repo.  
   **Path:** `M54_MASTER_IMPLEMENTATION_SPEC.md`  
   **Implication:** Freeze identifiers required by Rule 2 are present.  
   **Status:** Pass

2. **Finding:** Freeze checksum not reproducible under stated verification procedure.  
   **Path:** `M54_MASTER_IMPLEMENTATION_SPEC.md`  
   **Implication:** Master cannot serve as authoritative frozen contract until checksum validates.  
   **Status:** Block

3. **Finding:** Owner matrix coherent; asset_graph remains media lineage.  
   **Path:** master; `studio-api/app/asset_graph.py`; `studio-api/app/project_library/`  
   **Status:** Pass

4. **Finding:** Decision Records not deconflicted with Bible `production_decision` / `/decisions` API.  
   **Path:** master; `m211/decisions.py`; `bible/domain/schemas.py`; `bible/api_domain.py`  
   **Implication:** Competing decision stores remain possible.  
   **Status:** Block

5. **Finding:** Several “frozen contracts” remain prose-only (Wiki core records, Landing summary, format adapter, ops deep-link, creative plan envelopes, export payloads).  
   **Path:** master §3  
   **Implication:** Incompatible implementations allowed → Rule 4 Block.  
   **Status:** Block

6. **Finding:** Authority / proposal-first mutation ladder explicit.  
   **Path:** master; Bible schemas  
   **Status:** Pass

7. **Finding:** Project isolation on typed surfaces and reused systems.  
   **Path:** master; m211; bible; project_library; storyboard timeline_prep  
   **Status:** Pass

8. **Finding:** Performance budgets measurable with blocking thresholds.  
   **Path:** master §4  
   **Status:** Pass

9. **Finding:** Target UX tabs clear; current UI (`overview|library|production|plans|bible|approvals|jobs`) requires consolidation migration, not a second nav model.  
   **Path:** master; `CoDirectorProjectContent.tsx`; `navEntries.ts`  
   **Status:** Pass

10. **Finding:** Format adaptation = one core + adapters.  
    **Status:** Pass

11. **Finding:** Creative grounding via live registries; Unknown ≠ Ready.  
    **Path:** master; prompt_intelligence; provider-registry.json  
    **Status:** Pass

12. **Finding:** Timeline prep dual path — master `TimelinePreparationPayload` vs storyboard `TimelinePrepProposal` + `timeline_proposals.json` store — not resolved.  
    **Path:** master; `timelinePrep.ts`; `storyboard_studio/timeline_prep.py`  
    **Status:** Block

13. **Finding:** Export snapshot versions + checksum specified.  
    **Status:** Pass

14. **Finding:** Dreamweaver journey conceptually covered, but duplicate decision + timeline-prep systems would force parallel state.  
    **Status:** Block

## Unresolved risks (must clear before READY)

1. **Reproduce freeze checksum** (or re-stamp with a verified procedure).  
2. **Deconflict Decision Records:** freeze whether Bible `production_decision` is deprecated, migrated into m211-backed Decision Records, or read-only canon summary — never a second rationale store.  
3. **Schema-freeze** remaining prose contracts into typed DTOs under `m54.contracts.v1` (Landing, format adapter, Wiki article/assertion, ops deep-link, creative plans, export job payloads).  
4. **Single Timeline prep contract:** freeze whether storyboard `TimelinePrepProposal` is migrated into `TimelinePreparationPayload`, aliased, or retired — one payload, one store.

## Execution order (unchanged when READY)

```text
Phase 0 contracts → 1 Wiki+Memory → 2 Graph → 3 Bible sync → 4 Retrieval/tools
→ 5 Creative → 6 Landing/Ops → 7 Operator+History → 8 Export → 9 Cert
```

Do **not** begin Phase 0 implementation while this preflight is BLOCKED.

## Final verdict

**BLOCKED**

Named blockers:

1. Unreproducible master SHA-256 freeze.  
2. Competing decision architectures: m211 Decision Records vs Bible `production_decision`.  
3. Incomplete typed contract freeze (prose-only critical surfaces).  
4. Dual Timeline preparation contracts/stores unresolved.  
5. Dreamweaver journey would require parallel state until (2) and (4) are frozen.

---

```text
BLOCKED
```
