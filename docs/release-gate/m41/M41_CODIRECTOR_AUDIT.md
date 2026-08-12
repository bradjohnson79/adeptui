# M41 — Co-Director Production Completion Audit

| Field | Value |
|---|---|
| **Phase** | 4.1 — Co-Director Production Completion |
| **Date** | 2026-07-28 |
| **Product** | Adept UI Studio / Co-Director / Adept FilmWorks |
| **Authority** | Phase 4.1 brief; [`docs/design/ADEPT_UI_DESIGN_SYSTEM.md`](../../design/ADEPT_UI_DESIGN_SYSTEM.md) |
| **Prior coverage** | [`docs/m3.0a/CODIRECTOR_CAPABILITY_COVERAGE.md`](../../m3.0a/CODIRECTOR_CAPABILITY_COVERAGE.md), M32/M33 release gates |
| **Verdict (this audit)** | **NO-GO — audit baseline only; production completion not certified** |

---

## Purpose

This audit is Wave 0 of Phase 4.1. It classifies Co-Director subsystems honestly.

**Rule:** A tool name, prompt file, dropdown entry, or specialist registration is **not** proof of working integration.

Classification key:

| Label | Meaning |
|---|---|
| **Working** | Real round-trip with structured results; failures reported honestly |
| **Partially Working** | Path exists but incomplete, flaky, or limited scope |
| **Registered but Not Wired** | ID/prompt/UI present; handlers thin, blocked, or advise-only |
| **Scaffolded** | Schema/API/capability row exists; behavior stubbed or `partially_wired` |
| **Broken** | Claimed path fails for users |
| **Missing** | Required by Phase 4.1; not present |
| **Deferred** | Explicitly out of Version 1.1 / later phase |

---

## Executive summary

Co-Director today is a **strong conversational + proposal gateway** with a closed tool registry and human approval for mutations. It is **not** yet a complete production intelligence system:

- Specialists are **advise-only** (`may_execute_tools: false`).
- Editor place / subtitle / job-inspect tools are largely **missing** from the registry.
- Music/SFX **generate proposes** exist; timeline **place** lives outside the tool registry (m29).
- M2.14 / M2.13 capability IDs remain mostly **`partially_wired` scaffolds**.
- Compact/fullscreen shells exist (Phase 4.0 Aurora), with recent Options drawer fixes; full Phase 4.1 UX polish and cert workflow are **not done**.

**GO criteria from the Phase 4.1 brief are not met.** This document is the starting baseline for Waves 1–8.

---

## Architecture map

| Layer | Path | Notes |
|---|---|---|
| Gateway router | `studio-api/app/routers/codirector.py` | Chat, providers, conversations, proposals, tools |
| Core service | `studio-api/app/codirector/service.py` | Ollama/mock providers, chat composition |
| Tool registry | `studio-api/app/codirector/tools/{definitions,registry,execution}.py` | Closed bind table |
| Approvals | `studio-api/app/codirector/bible/proposals.py` | Propose → human approve → apply |
| Specialists | `studio-api/app/codirector/intelligence/*`, `prompts/specialists/*.md` | 32 prompts; advise-only |
| Plans | `intelligence/planning.py`, `m214/`, `m213/` | Multiple plan surfaces |
| UI session | `studio-web/src/components/CoDirector/CoDirectorSession.tsx` | Stream, persist, health |
| UI shell | `CoDirectorShell.tsx`, `Popup`, `FullScreen`, `ProjectContent`, `OverflowMenu` | Compact + fullscreen |

```text
User → CoDirectorSession → Ollama
                 ↓
           ToolRegistry (read | propose)
                 ↓
        Human Approve → apply → Bible / Library / m29 / jobs
                 ↓
        Specialists (advise only → synthesis)
```

---

## 1. Runtime and models

| Item | Class | Evidence / notes |
|---|---|---|
| Ollama provider probe | **Working** | `providers/ollama.py` → `/api/tags`; `GET /api/codirector/providers/{id}/health` |
| Assistant health | **Working** | `GET /api/assistant/health` (`ollama_reachable`) |
| Model selection in UI | **Partially Working** | Options → Model; persist via config store |
| Connection state machine (`Connected` / `Ollama unavailable` / …) | **Partially Working** | Health exists; Phase 4.1 explicit state UX + reconnect not fully specified in UI |
| Silent mock fallback | **Broken / risk** | Must remain disabled on production Beta; verify no silent mock in session open |
| Record provider+model on session | **Partially Working** | Chat outcomes carry model; formal session record needs audit in Wave 1 |

---

## 2. Session, context, persistence

| Item | Class | Evidence / notes |
|---|---|---|
| Conversation CRUD | **Working** | `GET/POST/DELETE /api/codirector/conversations/{project_id}` |
| UI message persist | **Working** | Session localStorage + API sync paths |
| Explicit project binding | **Partially Working** | `bindWorkspace`; fullscreen can open with **no project** (“No project” Overview) |
| Limited mode when no project | **Partially Working** | Chat works; production tools should refuse — enforce in Wave 1/3 |
| Context survives navigation / refresh | **Partially Working** | Conversations persist per project; active plan/memory needs Wave 7 cert |
| Canonical context (bible, characters, script, library, timeline) | **Partially Working** | Read tools exist for many domains; not yet one unified context contract |

---

## 3. Tool registry and confirmation

| Item | Class | Evidence / notes |
|---|---|---|
| Closed registry size | **Working** | **87** tools (50 read / 37 mutation), all handler-bound |
| Propose ≠ execute | **Working** | `tools/execution.py` |
| Human approval for mutations | **Working** | Proposal approve/reject APIs + `CoDirectorProposalCard` |
| Structured failure (category, evidence, retry) | **Partially Working** | Errors exist; Phase 4.1 uniform failure envelope incomplete |
| Invented success on failure | **Partially Working** | Enhance path historically had stub_copy fallback — treat as **Broken** until removed |
| Confirmation card richness (cloud, risks, providers) | **Partially Working** | Basic approve UI; Phase 4.1 card fields incomplete |

### Tool coverage vs Phase 4.1 required surface (summary)

| Domain | Class | Notes |
|---|---|---|
| Project / scenes reads | **Working** | e.g. `get_project_status`, `list_scenes` |
| Production Bible reads + proposes | **Working** | Summary/search/propose path |
| Character identity / Character Creator tools | **Working / Partial** | M33 stack; Korri cert still a GO gate |
| Provider / Comfy / Source Manager reads | **Working / Partial** | Health + readiness tools; stub-pack honesty needs Wave 3 |
| Scriptwriter propose | **Partially Working** | `propose_script_document`; full Phase 4.9 handoff incomplete |
| Music / SFX generate propose | **Partially Working** | `propose_music_generate`, `propose_sfx_generate` → library; not Editor place |
| Storyboard propose | **Partially Working** | Package yes; render often execution-blocked |
| Image / video / lipsync propose tools | **Registered but Not Wired / Missing** | Executive jobs exist; model tool coverage thin |
| Editor `editor.get_*` / `editor.place_*` | **Missing** | Placement via m29 `place_cue` / timeline_ops, **not** in closed registry |
| Job inspect / reconnect tool | **Missing** | Monitor remains PARTIAL |
| Continuity validation tool | **Partially Working** | Some bible/continuity proposes; actionable conflict UX incomplete |

---

## 4. Specialists and routing

| Item | Class | Evidence / notes |
|---|---|---|
| Specialist inventory | **Working** (as inventory) | **32** prompts under `prompts/specialists/*.md` |
| `may_execute_tools` | **Registered but Not Wired** | **All false** — specialists cannot run tools |
| Selector / runner / synthesis | **Partially Working** | Intent → specialist → advise → plan synthesis |
| Explicit specialist picker in UI | **Partially Working** | `CoDirectorSpecialistStrip` |
| Storyteller operational (canon → Scriptwriter) | **Partially Working** | Prompt + routing; not Phase 4.1 complete |
| Character Creator operational + Korri | **Partially Working** | M33 tools/certs; profile UI still a GO gate |
| Director 2.0 structured handoff | **Partially Working / Broken path** | Timeline/executive pieces exist; prompting timeline visibility/results need Wave 5 fix |
| Audio / Editing specialists | **Registered but Not Wired** | Advise-only; no place tools |

---

## 5. Production plans and jobs

| Item | Class | Evidence / notes |
|---|---|---|
| M2.4 `ProductionPlan` | **Partially Working** | Built via intelligence; DB-backed |
| M2.14 plan view / stages | **Scaffolded** | Many capability IDs `partially_wired` |
| M2.13 A–Z scene protocol | **Scaffolded** | `partially_wired` |
| Plan states (pending→complete/cancelled) | **Partially Working** | Not fully Phase 4.1 state machine |
| Long-running job reconnect in Co-Director | **Missing / Partial** | Jobs exist on projects; no first-class Co-Director job tool |
| Multi-step partial completion honesty | **Missing** | Required for Wave 4/8 |

---

## 6. Workspace integrations

| Workspace | Class | Notes |
|---|---|---|
| Production Bible | **Working** (read/propose) | Mutations need approval |
| Character Profiles | **Partially Working** | M33; Korri display/save still cert-critical |
| Scriptwriter | **Partially Working** | Propose + specialist; `@` resolve + revision history incomplete for M41 |
| Director 2.0 | **Partially Working** | Fix existing handoff; do not add parallel UI |
| Project Library | **Partially Working** | Awareness tools (M30J); registration lineage completeness varies |
| Source Manager / providers | **Partially Working** | Read readiness; install never without approval |
| Image / Video generation | **Partially Working** | Certified product routes (M32) exist; Co-Director tool path incomplete |
| Voice / dialogue | **Partially Working** | Voice Profile stack exists; Co-Director must not silent-Kokoro |
| Music / SFX | **Partially Working** | Propose generate; place on timeline via m29 not tool-wired |
| Lip Sync (LatentSync) | **Partially Working** | Certified WAN/LTX paths; Co-Director launch tool incomplete |
| Editor | **Registered but Not Wired** | Specialist advise; no registry place/gain/fade tools |
| Subtitles | **Missing / Partial** | Not Phase 4.1 complete from Co-Director |
| Export | **Partially Working** | Product export exists; Co-Director-driven export incomplete |

---

## 7. UI (Aurora / Phase 4.0 preserve)

| Item | Class | Evidence / notes |
|---|---|---|
| Compact popup | **Working** | `CoDirectorPopup.tsx` + cinematic shell |
| Fullscreen Chat + Project Content | **Partially Working** | `CoDirectorFullScreen` / `CoDirectorProjectContent`; SplitPane polish ongoing |
| Options drawer theme | **Working** (recent) | Aurora dark overflow; was light-panel / crushed by flex |
| Options button | **Working** (recent) | Toggle + `flex-shrink: 0` so panel visible |
| No sample/fake approvals | **Partially Working** | Verify M2.14 sample seeds removed in Wave 2 |
| Structured result cards | **Partially Working** | Proposal cards exist; generation/timeline cards incomplete |
| Invisible text / light cards | **Working** for overflow | Broader CSS migration still tracked under M40 |

---

## 8. Memory, security, errors

| Item | Class | Notes |
|---|---|---|
| Project-scoped memory store | **Partially Working** | `m211/memory.py` |
| No cross-project leak | **Partially Working** | Needs Wave 7 tests |
| Cloud / cost / upload disclosure | **Partially Working** | Must be explicit on cloud routes |
| Secret / token never exposed | **Working** (intent) | Keep redaction in Source Manager / CLI paths |
| Actionable error recovery | **Partially Working** | Generic failures still common |

---

## 9. Testing and prior certification

| Evidence | Role for M41 |
|---|---|
| M32 Co-Director UI / Hitchhiker / generation gates | Product routes work; not Co-Director tool-complete |
| M33 Character Creator / Korri reports | Character stack; re-cert required for M41 GO |
| M30J library awareness | Library tools baseline |
| `studio-api/tests/test_codirector_*.py` | Unit coverage of tools/provider/intelligence |
| `tests/e2e/codirector/*`, `tests/e2e/m32*` | UI/lifecycle e2e |
| **M41-CD-01…40** | **Missing** — not implemented |
| **M41 cert workflow** (Korri scene → Director → media → voice → music/SFX → Editor → reload) | **Missing** |

---

## 10. Adjacent work landed (not Phase 4.1 completion)

These improve the studio shell around Co-Director but **do not** satisfy Phase 4.1 GO:

- Live System Status gauges (real probes; no fake Bible/Intelligence pills).
- Co-Director Options Aurora theme + Options panel flex visibility fix.
- Source Manager GH/HF CLI detection / auth UX (earlier thread).

---

## 11. Required Phase 4.1 report package (status)

| Report | Status |
|---|---|
| `M41_CODIRECTOR_AUDIT.md` | **This document** |
| `M41_IMPLEMENTATION_REPORT.md` | Pending Wave 1–7 |
| `M41_SPECIALIST_AGENT_MATRIX.md` | Pending Wave 5 |
| `M41_TOOL_REGISTRY_REPORT.md` | Pending Wave 3–6 |
| `M41_TEST_REPORT.md` | Pending Wave 8 |
| `M41_CODIRECTOR_CERTIFICATION_REPORT.md` | Pending Wave 8 |

---

## 12. Recommended implementation order (from plan)

1. **Wave 1** — Runtime honesty + project-bound sessions + reconnect  
2. **Wave 2** — Compact/fullscreen polish; remove fake approvals  
3. **Wave 3** — Canonical read tools + `@` resolve + provider honesty  
4. **Wave 4** — Plan states, confirmation cards, job inspect, kill stub success  
5. **Wave 5** — Specialist matrix + Storyteller / Character Creator / Director 2.0 + Korri  
6. **Wave 6** — Image/video/voice/music/SFX/lipsync/editor place/subtitle tools  
7. **Wave 7** — Memory, history, errors, privacy  
8. **Wave 8** — M41-CD-01…40 + real cert + remaining reports  

**Preference:** Wire existing registered IDs and m29/timeline_ops behind the closed registry; do not invent parallel sources of truth.

---

## 13. Final audit verdict

| Question | Answer |
|---|---|
| Is Co-Director a complete production intelligence system? | **No** |
| Can it chat + propose with approval? | **Yes (Working baseline)** |
| Are specialists tool-enabled? | **No** (advise-only) |
| Can it generate music/SFX and place them on a saved Editor timeline via tools? | **No** (generate propose Partial; place Missing in registry) |
| Does the Phase 4.1 end-to-end cert pass? | **Not run** |
| Gate decision | **NO-GO — Co-Director is not yet a complete production intelligence system** |

Proceed to Wave 1 only after this audit is accepted as the baseline.
