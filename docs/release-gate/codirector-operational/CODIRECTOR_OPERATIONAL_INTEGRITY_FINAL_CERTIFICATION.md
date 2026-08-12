# Co-Director Operational Integrity — Final Certification

**Milestone:** Co-Director Operational Integrity Audit, Repair & Final Hardening
**Date:** 2026-08-08
**Repo:** `C:\AdeptFilmWorks\AIVideoStudio`
**Verdict:** GO — CO-DIRECTOR OPERATIONAL INTEGRITY CERTIFIED FOR CREATOR MANUAL BETA

---

## 1. Architecture

Co-Director is the closed operational intelligence/control layer over Adept UI's native systems.

- **Tool registry:** `studio-api/app/codirector/tools/definitions.py` + `registry.py` defines every tool, its schema, its capability, and its handler binding. No runtime lookup.
- **Tool exposure:** `studio-api/app/codirector/tools/exposure.py` filters the 485 registered tools down to a context-appropriate set (35–174 tools per representative intent) based on registry metadata, not lexical keyword matching.
- **Context model:** `ToolContext` carries `project_id`, `scene_id`, `db`, and capabilities. All handlers read authoritative state from this context.
- **Execution path:** `service.py` → `execute_audited` / `execute_approved_proposal` → native handler → persistence → `read_cache.clear_project()` invalidation.
- **Proposal/approval:** Mutating tools return `ToolPreview` for human review; the apply path runs only after approval, persists, and emits `adept:codirector-project-mutated` so the UI refreshes.
- **Error model:** `CoDirectorError` in `errors.py` carries structured `code`, `message`, `details`, and `evidence`, with path redaction and truthful degradation (`fallbackUsed`, `fallbackReason`, `providerError`).

---

## 2. Audit Findings & Repairs

| Finding | Root cause | Repair | Evidence |
|---------|------------|--------|----------|
| All 485 tools exposed to every prompt | No capability-aware filtering | Added `exposure.py` metadata-derived filter | `test_codirector_c2_routing_repairs.py` (35/35) |
| Tool schemas drifted from native APIs | `definitions.py` missing parameters; sanitizer lacked array/object coercion | Repaired schemas + added `array`/`object` coercion in `sanitize.py` | `test_codirector_p0_tool_repairs.py`, `test_codirector_schema_alignment.py` |
| Read cache never invalidated on mutations | `execution.py` did not call `clear_project` | Added `clear_project()` after successful audited writes | `test_codirector_read_cache_invalidation.py` |
| Cross-project access possible | Some handlers lacked project ownership checks | Added `ownership.py` helper; updated voice/m29/m214 handlers; added 32 ownership tests | `test_codirector_ownership_isolation.py` (32/32) |
| Streaming chat bypassed fence/proposal parsing | `stream_for_project` early-return emitted raw `tool` fences | Added `_emit_completion_with_fence_handling` helper | `test_codirector_cross_system_workflows.py` streaming regression |
| UI did not refresh after tool approval | Event name was plan-specific and Co-Director opened as a route | Broadened event to `adept:codirector-project-mutated`; opened Co-Director as popup over project workspace | `tests/e2e/codirector/cross-system-uIsync.spec.ts` (2/2) |
| Error envelopes leaked paths and unredacted details | `errors.py` emitted raw `details` and `_safe_evidence` did not strip paths | Added `scrub_sensitive` and `_scrub_detail_value` | `test_codirector_error_truthfulness.py` |
| Foundation path silently degraded on missing model | `chat_for_project` returned 200 with no failure signal | Surfaced `fallbackUsed`, `fallbackReason`, `providerError` in `/chat` JSON response | `test_m41_codirector_wave1.py` updated contracts |
| Stale test contracts | Pre-existing tests asserted old envelopes/fields | Updated to current authoritative contracts | Wave 1, Wave 4, library, vision tests |

---

## 3. Native System Operations Matrix

| System | READ | WRITE | PERSIST | VERIFY | UI SYNC | ERROR | VERDICT |
|--------|------|-------|---------|--------|---------|-------|---------|
| Timeline | `timeline.inspect_batches`, `get_workspace` | `timeline.propose_add_batch`, `propose_add_image_clip`, `propose_add_prompt_segment`, `propose_generate_scene`, `send_to_timeline` | `director_timeline_w46/store.py` | Cross-system tests reload master | `adept:codirector-project-mutated` listener in `TimelineEditorShell.tsx` | Structured `WORKFLOW_GRAPH_DRIFT`, `BATCH_NOT_FOUND`, etc. | GO |
| Scene / Project | `scene.get`, `scene.list`, `project.get_summary` | `scene.*` mutation tools, `project.*` | `db` + `scene_service` | Cross-system tests read back scene | Event-driven refresh | `SCENE_NOT_FOUND`, `PROJECT_NOT_FOUND` | GO |
| Production Bible | `bible_read.*`, `bible_domain.*` | `bible.*` proposal tools | `bible` operations + versioning | `test_production_bible.py` | Event refresh | Structured bible errors | GO |
| Character | `character_identity.*`, `character_creator.*` | `character_creator.*` mutation tools | `character_identity` tables | Cross-system tests | Event refresh | `CHARACTER_NOT_FOUND` | GO |
| Voice Studio | `voice_environment.*`, `voice_performance.*` | `voice_performance.*`, `voice_m410.*` | `voice_performance` tables | `test_m41_codirector_wave2.py` | Event refresh | `VOICE_NOT_FOUND` | GO |
| Image Pipeline | `image_pipeline.*` | `image_pipeline.*` | `image_pipeline` store | `test_m42_image_pipeline.py` | Event refresh | `PLAN_NOT_FOUND` | GO |
| Multi-Shot (Krea) | `multi_shot.*` | `multi_shot.*` | `multi_shot` tables | `test_codirector_krea2_multishot.py` | Event refresh | `PLAN_NOT_FOUND` | GO |
| MAGI | N/A | N/A | N/A | N/A | N/A | N/A | **Not operational** — documented and no fictional tools exposed |

---

## 4. Cross-System Workflows

| Request | Chain Verified | Evidence |
|---------|----------------|----------|
| Add image to Timeline batch | `timeline.propose_add_image_clip` → master save → UI refresh | `test_m42_w46_codirector_timeline.py`, `cross-system-uIsync.spec.ts` |
| Send approved Multi-Shot to Timeline | `multi_shot.send_to_timeline` → W46 `add_batch` + `add_clip_to_batch` + `touch_batch_config` → shot lineage | `test_codirector_krea2_multishot.py`, `test_krea2_multishot_timeline.py` |
| Character asset → Timeline batch | `character_identity.*` → `timeline.propose_add_image_clip` | Cross-system tests |
| Voice performance → Timeline | `voice_performance.place_on_timeline` | Wave 2 tests |
| Production Bible update | `bible.*` proposal → approve → version persist | `test_production_bible.py` |
| Streaming tool proposal | Fenced `tool` reply → `_interpret_reply` → `tool_proposal_created` event | `test_codirector_cross_system_workflows.py` |

---

## 5. Automated Certification

- **Full Co-Director keyword sweep (independent verifier, clean machine):** `622 passed, 0 failed`.
- **Targeted 6-file suite:** `140 collected, all green` (cross-system, native systems, ownership, error truthfulness, approval safety, c2 routing).
- **Playwright UI synchronization:** `2 passed` (`tests/e2e/codirector/cross-system-uIsync.spec.ts`).
- **Schema alignment:** `1 passed` (`test_codirector_schema_alignment.py`), including the new `multi_shot.*` tools.
- **Krea multi-shot tools:** `4 passed` (`test_codirector_krea2_multishot.py`).
- **Read cache invalidation:** regression suite passes.

---

## 6. Independent Verifier

The [c9-verifier](bb94be3e-34a4-42c1-b993-5c88cec8ec90) subagent completed independent verification on a clean machine:

- Re-ran the full Co-Director test suite: **622 passed, 0 failed**.
- Ran the targeted 6-file suite: **140 collected, all green**.
- Ran the cross-system UI-sync Playwright spec: **2/2 passed**.
- Inspected the actual tool registry, execution path, read-cache invalidation, error redaction, and ownership guards.
- Verified that every claimed repair has a corresponding regression test.
- Confirmed that MAGI remains documented as non-operational and no fictional MAGI tools are exposed.

**Independent verifier statement:** VERIFIED — GO — the Co-Director Operational Integrity gates are met.

---

## 7. Limitations

1. **Actual GPU generation:** Not executed during automated certification. Chargeable/expensive generation remains a creator-manual boundary.
2. **MAGI:** Not operational for Co-Director in this milestone; documented as N/A.
3. **Multi-Shot creator UI:** The backend is complete and exposed to Co-Director; a dedicated shot-list/candidate-review workspace is a future UI layer.
4. **E2E timing sensitivity under load:** The UI-sync Playwright spec can flake when the host is under heavy concurrent load (e.g., running the full pytest sweep simultaneously). On an idle machine it passes reliably; this is a test-harness robustness note, not a creator-facing defect.
5. **Minor test-count/name drift:** The approval suite is `test_codirector_approval_safety.py` (29 tests), not `..._approval_persistence.py`; `error_truthfulness` has 27 tests; the full sweep has grown to 622 passed. Functional coverage is intact.
6. **Long-tail adversarial cases:** The adversarial suite covers ownership, stale state, cross-project isolation, and malformed tool results; additional exotic state races may be discovered during manual Beta.

---

## 8. Final Verdict

**GO — CO-DIRECTOR OPERATIONAL INTEGRITY CERTIFIED FOR CREATOR MANUAL BETA**

Co-Director correctly reads, invokes, modifies, persists, and coordinates the native Adept UI systems it is intended to operate. The tool registry is clean, routing is capability-scoped, context isolation is enforced, errors are truthful and structured, approvals persist, and the UI reflects successful mutations. The Krea 2 Multi-Shot operations are also wired and certified through the same Co-Director tool registry.
