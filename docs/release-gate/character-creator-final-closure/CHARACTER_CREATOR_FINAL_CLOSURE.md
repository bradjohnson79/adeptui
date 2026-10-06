# Character Creator Final Closure — Unified Completion

**HISTORICAL / SUPERSEDED (Law 30).** This report is not the governing document for Character Creator. Do not treat its `PARTIAL` / cert-script Rev 4 evidence as a GO. Current governing contract:

`docs/release-gate/character-creator-4view-json/CHARACTER_CREATOR_4VIEW_JSON_CLOSURE.md`

---

**Law 30 (historical):** this was the only governing report for Character Creator Final Full-Stack Closure. Historical Character Creator reports remain historical. This pass supersedes the earlier `NO-GO — CHARACTER CREATOR FINAL CLOSURE INCOMPLETE` in this file. Image / Prop / Brand coverage is **not** recertified here.

**Date:** 2026-08-22 / 2026-08-23  
**Branch:** `feat/character-creator-final-closure`  
**HEAD (committed):** `1c865606571664ed3c06dffdf468f643cd9a3da8`  
**Working tree:** dirty. Do not commit. Do not reset. Do not deploy. Do not treat HEAD as the closure tree.

**Project:** Schnick Coffee `2347bf46-3762-4763-86c5-4a6032522278`. Korri `c49371ed-ba6b-4c16-ba98-a8b28b72118b`. No `POST /api/projects` for this lifecycle.

**Creator UI:** Vite `http://127.0.0.1:5173/` + Studio API `http://127.0.0.1:8758/`. Retired `:8760` was observed listening and was **not** used.

Peer review (this section is filled after GLM 5.2 + Kimi K3 return):

| Reviewer | Model | Verdict |
| --- | --- | --- |
| A | GLM 5.2 (`glm-5.2-max`) | PENDING |
| B | Kimi K3 (`kimi-k3-max`) | PENDING |

## Verdict

```text
REVIEW PENDING — GLM 5.2 + KIMI K3
```

Builder evidence below is complete enough for review. Allowed final language will be written only after both reviews and any required remediations:

- `GO — ADEPT UI CHARACTER CREATOR FULL-STACK PRODUCTION CERTIFIED`
- else `PARTIAL` / `NO-GO` / `BLOCKED BY ENVIRONMENT` with the exact blocker

Related surgical item from the prior session (not the CC binary gate):

```text
GO — SPATIAL MAP LIBRARY + UPLOAD BUTTON WIRING
```

---

## Root causes closed this pass

1. **2509 UNET not Comfy-visible.** File already on `D:\01_Models\Qwen\ComfyUI\split_files\diffusion_models\qwen_image_edit_2509_fp8_e4m3fn.safetensors` (~20.43 GB). Mapped with extra-paths `adept_qwen_edit_2509` in `%APPDATA%\Comfy Desktop\shared_model_paths.yaml` (backup `shared_model_paths.yaml.cc-final-closure.bak`). No new HF download. No DiffusersLoader. No 58 GB shard copy.
2. **Reject refused Flux drafts.** Flux CRS candidates are tagged `imagegen`, not `character_sheet`. Reject now treats pack-listed draft IDs as owned and unlinks `imagegen*` files.
3. **Reject leftovers.** Same reject service now removes previous-version copies, deletes Asset rows/files, dismisses Co-Director packs that only pointed at those assets, and terminalizes matching jobs. Canon / `persist_crs` / approved hero are not bumped.
4. **Failed leftover cards.** `JOB_NOT_FOUND` is not retried. Dismiss persists (`CANCELLED` + `error="DISMISSED"`). No new `ExecutionStatus.DISMISSED` enum (frozen contract).
5. **Previous versions.** UI/API history lists approved historical revisions only, excluding the current hero.
6. **Generator honesty.** Character roster hides non-executable families (`sd15` never shown; `krea2` hidden unless Certified). 2509 appears only when `runtimeReady`. AUTO stays Flux-primary / Qwen 2512 fallback and does not pick Draft 2509. Vite parse typo `.map((m) => ({)` in `CharacterGeneratorPanel.tsx` was repaired; Auto is a visible first option so the selector is not blank.
7. **Stuck ImageProduct queue.** After a hung Comfy wait, DB rows stayed `queued` with empty Comfy queue. Adept-owned API restart + cancel of leftover queued jobs restored the worker. Jobs then ran on GPU.

---

## Generator / workflow matrix (live roster)

`GET /api/imagegen/models?surface=character`

| Family | Shown | Status | Ready | CC route used this pass |
| --- | --- | --- | --- | --- |
| auto | Yes | — | — | Backend AUTO = Flux, then Qwen 2512. Never `qwen2512.ref`. Never invented `{fam}.ref_edit`. |
| qwen_edit_2509 | Yes | Draft | Runtime Ready | Synthetic I2I `qwen_edit_2509.crs_single_view` **PASS**. Korri generate **400** fail-close: 2509 refuses a full CRS as the edit canvas when no proven one-figure crop exists. |
| qwen2512 | Yes | Certified | Ready | Available. Not used for live Korri generate. |
| flux | Yes | Certified | Ready | Live Korri generate / reject / approve: `flux.txt2img` / `CRS_VIEW_GENERATION`. |
| illustrious | Yes | Certified | Ready | Shown because executable. Not used for live Korri generate. |
| krea2 | Hidden | — | — | Not Certified. |
| sd15 | Hidden | — | — | Never shown. |

---

## Live 2509 synthetic I2I (not Korri)

| Field | Evidence |
| --- | --- |
| Job | `d8f7fe41-ac7c-4a4e-8fb3-d5c6a70948c5` |
| Workflow | `qwen_edit_2509.crs_single_view` |
| Source asset | `e9d4b5af-5779-4902-8027-b939589301a2` |
| Output asset | `cd64ae0f-c78a-4a9a-8b67-d1158f4b1f34` |
| File | `GET /api/assets/{id}/file` **200**, `image/png` |
| GPU | RTX 5090, **~31 GB VRAM, 99% util**. No silent CPU fallback. |
| Health | `/api/health` 200 during the successful run |
| Interrupted first attempt | `56c718c2-84c1-4563-92e3-4cb9610af76e` — API restart, not missing model |
| Artifacts | `evidence/discover_qwen_edit_2509.json` (`runtimeReady: true`), `object_info_2509_post.json`, `synthetic_2509_job2.json`, `synthetic_2509_gpu_samples2.json` |

---

## Live Korri lifecycle (Schnick only, `candidateCount=1`)

Persist CRS is authoritative. Pack `crsRevision` / `nextCandidateRevision` is pack numbering and was **not** used as canon.

| Step | Result | IDs |
| --- | --- | --- |
| Starting canon | Approved `b6ab91dd-9d0a-4e4b-98b4-b26d268950dc`, persist **rev 3** | — |
| 2509 on Korri | **400** honest fail-close (CRS cannot be 2509 canvas without a proven identity crop) | — |
| Generate 1 (Flux) | Candidate preview 200 | `e0a9d984-95ff-4487-a802-5f69e6ba89df`, workflow `flux.txt2img`, provenance `LOCAL — FLUX.1 Kontext`. Canon still `b6ab91dd` / 3 |
| Reject 1 | **200**, file **404**, leftover candidates `[]` | `rejectedAssetIds=[e0a9d984-…]`. Canon untouched |
| Generate 2 (Flux) | Preview 200, then reject **200**, file **404** | `57ef016a-446a-4ab5-8fd4-d11be06f8d6e`. Canon still `b6ab91dd` / 3 |
| Generate 3 (Flux CRS_VIEW_GENERATION) | Job **done**, preview **200** / 2,334,250 bytes | Job `c06984d7-3797-43f1-b6cf-86ca3cac45b7`, Comfy `586aeccf-2331-4fbc-a3ae-70a9964d1810`, candidate `5be851a2-92c1-4342-9f13-f0b1abecdeee`. Canon still `b6ab91dd` / 3 |
| Approve | **200**, persist **rev 3 → 4** | Approved `5be851a2-…`, reference `d00958e4-9a87-4f7a-9359-d0f6b8b45065` |
| Reload `GET /crs` | Same approved asset, rev **4** | — |
| Korri DELETE | **409** `PROTECTED_CHARACTER`. Korri still `APPROVED` | — |
| Disposable delete | Create `a9c44a2e-…` → DELETE 200 → GET **404** | Inside Schnick |
| Queue | Comfy running=0 pending=0. `/api/health` 200 | — |

Artifacts: `evidence/korri_generate3.json`, `evidence/korri_approve_delete_proof.json`.

---

## Tests (exact counts)

| Suite | Result |
| --- | --- |
| API `test_reject_character_candidate.py` + `test_character_creator_final_closure.py` + `test_qwen_edit_2509.py` + `test_capability_label_draft.py` + `test_character_lifecycle_controls.py` | **25 passed** |
| Web vitest `approvedHistoricalRevisions` + `characterGeneratorPanel.presence` + `characterGeneratorPlan` + `failedExecutionCards` | **4 files, 35 passed** |
| Playwright `tests/e2e/character-creator/character-final-closure.spec.ts` against `http://127.0.0.1:5173` + `http://127.0.0.1:8758` | **2 passed** (last clean run 14.4s). Console errors **[]**. Unexplained 422/500 **[]**. |
| Scene / ERS AUTO suites | **Not run** (out of scope) |

Playwright screenshots: `evidence/pw-korri-selector.png`, `pw-korri-approved-preview.png`, `pw-korri-reload.png`, `pw-disposable-deleted.png`, `pw-console-network.json`.

Playwright verified selector honesty, approved Korri CRS persist/reload (Revision 4, 2048×2048 preview), and disposable delete inside Schnick. It did **not** click Generate on Korri after approve (avoids a second 2048 Flux job). Live Generate / Reject / Approve were proven on the Studio API + Comfy path above.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — Schnick → Character Creator → Korri |
| Frontend | PASS — Vite 5173 Character Creator; approved CRS Revision 4 visible after reload |
| API | PASS — generate / reject-candidate / approve-candidate / CRS GET / delete 409 |
| Backend | PASS — visual-sheet + persist CRS; AUTO executable-only |
| Persistence | PASS — rev 3 → 4; reload returns `5be851a2` |
| Runtime | PASS — Comfy Flux `flux.txt2img` on RTX 5090; 2509 synthetic I2I also PASS |
| Result | PASS — preview 200; rejected IDs 404 |
| Reload | PASS — Playwright + `GET /crs` |
| Downstream | PASS — Korri still resolvable; `@Korri is ready everywhere`. Library file for approved asset 200. Rejected files 404 |

---

## Files changed (Character Creator set; dirty tree also has unrelated hunks)

Allowed / touched for this closure:

- `studio-api/app/character_identity/visual_sheet.py` — reject ownership, AUTO executable-only, 2509 fail-close
- `studio-api/app/character_identity/service.py` — approve stamps previous hero
- `studio-api/app/codirector/execution/cancel.py` + `api.py` — leftover dismiss
- `studio-api/app/imagegen_workflows.py` — executable CC roster
- `studio-web/src/components/character/**` — reject, history, generator filter, Auto option, Vite parse fix
- `studio-web/src/components/CoDirector/failedExecutionCards.ts`, `AgentWorkSurface.tsx`, `CoDirectorMessage.tsx`, `CoDirectorSession.tsx`
- `studio-web/src/api.ts` — `dismissExecution`
- `studio-api/tests/test_reject_character_candidate.py`, `test_character_creator_final_closure.py`
- `tests/e2e/character-creator/character-final-closure.spec.ts`
- `docs/release-gate/character-creator-final-closure/**`

Shared `compile.py` 2509 Draft-allow hunk was already present. Do not recertify Image/Prop/Brand.

---

## Limitations

- Dirty mixed tree. No commit.
- 2509 is **Draft / Runtime Ready**, not Certified. AUTO must not select it.
- Korri 2509 generate is blocked until a proven one-figure identity crop exists. That is fail-close, not a silent fallback.
- Studio API can die or leave ImageProduct jobs `queued` while Comfy is empty. Adept-owned restart recovers; do not restart during an in-flight generate.
- Playwright did not click Generate / Reject / Approve on Korri after the live approve (API already proved those writes).
- Leftover-card dismiss is unit/API proven; Playwright did not inject a `JOB_NOT_FOUND` card.
- `:8760` was up and unused. Do not treat it as the creator UI.
- No Vercel / hosted product certification.
- Coverage remains `EXCLUSION — CHARACTER CREATOR REMAINS UNCERTIFIED` until this report’s final allowed GO lands.

---

## Owner-path double-check

- One project: Schnick. Korri never deleted.
- Delete proof used a disposable Schnick character only.
- Reject deletes candidate assets; approve is the only persist-CRS writer.
- Generate / regenerate did not overwrite persist CRS (rev stayed 3 until approve).
- GPU-first: 2509 synthetic showed 99% util / ~31 GB; Flux Korri job completed in Comfy (`comfy_prompt_id` set). No silent CPU fallback.
- Creator UI is Adept Character Creator, not raw Comfy.

---

## FINAL

```text
REVIEW PENDING — GLM 5.2 + KIMI K3
```
