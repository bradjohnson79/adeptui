# Co-Director Creation Intelligence — Certification Report

**Governing:** [00-GOVERNING.md](./00-GOVERNING.md)  
**Branch:** `feat/codirector-temporal-continuity`  
**HEAD:** `c8c5133` (working tree includes Revision B; not committed)  
**Independent verifier:** [Revision B verifier](e10dedb2-ed2c-4d69-a9e8-fc4688675790) — `READY FOR PRIMARY REVIEW`

## Verdict

```text
E2E BLOCKED — live Beta API :8758 is a stale adopted process without /api/perception; Character / Schnick / Edit GPU visuals not run
```

This is not `CERTIFIED COMPLETE — FULL-STACK E2E VERIFIED`. Backend and isolated Playwright are not a substitute for the three live visual scenarios.

## What was implemented

Architecture A only. Sibling `SpatialDraft`. No `zones[]` on `SpatialMapDocument`. 4/4/4 slots remain visible. Chat is not required.

| Phase | Result |
|---|---|
| 0 Contracts | IMPLEMENTED |
| 1 CD Scene Review | IMPLEMENTED |
| 2 Geometry worker + dedicated installer | IMPLEMENTED (Testing; venv created at install; no silent API Python fallback) |
| 3 Scene NL compile | IMPLEMENTED |
| 4 Auto-mask honesty + CC copy + leak detector | IMPLEMENTED |
| 5 CC Approve registration | IMPLEMENTED |
| 6 Live visual cert | NOT VERIFIED |

## Tests (measured)

| Suite | Result |
|---|---|
| `studio-api/tests/test_creation_perception.py` | **21 passed** |
| `test_scene_creator_mini_fidelity.py` + `test_movement_packet_isolation.py` + `test_scene_creator_grounding.py` | **included in 61 passed** (with perception packet tests) |
| Spatial / engine regression (`test_spatial_map_attach_projection.py`, `test_engine_ownership.py`, `test_spatial_placement_integrity.py`) | **30 passed** |
| Frontend vitest (CD Scene Review, Smart Select, CC copy, sheet stage, provenance) | **24 passed** |
| Playwright `revision-b-creation-intelligence.spec.ts` against current-code API `:8742` + Vite `:5174` | **5 passed** |

Playwright first failed when the browser or request client hit stale `:8758` (`{"detail":"Not Found"}`). After pointing both the request helper and Vite proxy at `:8742`, all five passed.

## Live environments

| Surface | Status |
|---|---|
| Adept UI Beta web `http://127.0.0.1:8760/` | HTTP 200 after rebuild + supervisor start (HEALTHY) |
| Studio API `http://127.0.0.1:8758/` | HTTP 200, `apiRevision=c8c5133`, started `2026-08-20T06:45:22Z`, **adopted**, **no `/api/perception`** |
| Current-code API `http://127.0.0.1:8742/` | HTTP 200, `/api/perception/capability` returns sceneReview=available, geometry=unavailable, chatRequired=false |
| Current-code Vite `http://127.0.0.1:5174/` | HTTP 200, proxies `/api` to `:8742` |

Stop/restart of `:8758` was refused by the OS from this session (`PID 58504` listens but is not visible to `taskkill` / `tasklist`). Supervisor marked it adopted and will not replace it.

## Visual scenarios

| Scenario | Status |
|---|---|
| 1 Character CRS consistency | NOT VERIFIED — no live Qwen/GPT Image 2 Approve → Scene Creator still |
| 2 Schnick spatial blocking | NOT VERIFIED — no live Atlas + Accept + NL generate pixels |
| 3 Edit preservation | NOT VERIFIED — leak detector exists; no live `zimage.inpaint` unmasked delta |

`zimage.inpaint` was **not** given FLUX post-composite. Synthetic leak tests pass. Live leak is unmeasured.

## E2E TRACE

| Stage | Result |
|---|---|
| User action | PASS — “Review this scene” / Accept chrome present; slots remain |
| Frontend | PASS — `CdSceneReview` on Spatial Map; Smart Select honest |
| API | PASS on `:8742` / FAIL on live Beta `:8758` |
| Backend | PASS — review does not write slots; Accept uses place_* only |
| Persistence | PASS — SpatialDraft trait + corrections by label |
| Runtime | N/A — geometry weights not installed; geometry=unavailable |
| Result | FAIL — no live generated stills for the three visual gates |
| Reload | PASS — draft persist contract + Playwright review-without-write |
| Downstream | N/A — ERS/Scene generate visuals not run |

## Independent verifier

[Revision B verifier](e10dedb2-ed2c-4d69-a9e8-fc4688675790) returned `READY FOR PRIMARY REVIEW`.

- MUST 1–4, 6–11: PASS
- MUST 5 was FAIL (venv never created). Repair landed after that pass: `ensure_stills_perception_venv()` on install; `worker_python()` no longer falls back to Studio API Python.
- Live visual cert: **NOT OBSERVED**

## Frozen systems checked

- `SpatialMapDocument` has no `zones`
- `gpu_lease.py` has no stills edits
- `REQUIRED_FOR_GENERATION` unchanged
- Geometry catalog rows `required=False`, installer `stills_perception_hf` before Hunyuan
- Single-CRS Character Creator preserved
- `queue_worker.py` still skips native inpaint composite

## Manual review path

1. Use **current-code** UI at `http://127.0.0.1:5174/` (or any client pointed at `:8742`). Do not expect CD Scene Review to work through Beta `:8760` → `:8758` until that API process is replaced.
2. Open Spatial Map. Confirm Character / Prop / Camera slots are still there.
3. Click **Review this scene**. Accept suggestions into slots. Save.
4. In Scene Creator, type ordinary blocking language (`behind`, `beside`, `facing`, `customer side`). Generate is a separate GPU gate.
5. Region edit: **Select from the scene** must tell you to paint; the brush stays.

## Limitations

- Live Beta product path is split: new frontend can be on `:8760`, old API on `:8758`.
- Geometry models are not downloaded. Capability stays Testing/Unavailable.
- Isolated venv is created at Setup install; CUDA Torch is **not** auto-installed (Law 26).
- No hosted Vercel evidence.

## Final language

```text
E2E BLOCKED — live Beta API :8758 is a stale adopted process without /api/perception; Character / Schnick / Edit GPU visuals not run
```
