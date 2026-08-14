# SCENE CREATOR EXPRESS + STANDARD — COMPLETION REPORT

**Date:** 2026-08-14  
**Branch:** `beta`  
**Starting SHA (this session):** `8b6ddf9850fcb461ea9facc5e910ae8a62664b34`  
**HEAD before this commit:** `985b72dd2277ea6fd480e1bc4071e19b69d1d998`  
**Governing audit:** [`SCENE_CREATOR_EXPRESS_STANDARD_AUDIT.md`](./SCENE_CREATOR_EXPRESS_STANDARD_AUDIT.md)  
**Independent verifier:** [Re-verify Scene Creator](88e750ff-1931-49d3-8512-1be3413dfb8d) — **READY FOR MANUAL BETA**

Playwright is out of scope. Final live gate is Manual Beta (Express A–O + Standard A–G).

---

## Verdict

**NO-GO**

Implementation, automated tests, production build, Beta refresh, and independent verification are complete. Product GO requires creator Manual Beta. Do not treat READY FOR MANUAL BETA as GO.

---

## What shipped

One shared Scene Creator core. Co-Director Express and Production Standard are views over `useSceneCreator` / `SceneCreatorCore`. No second backend. Scene Master Sheet is not Scene Creator.

| Law | Implementation |
|---|---|
| ERS first | Creator identity is `sheetId`. Resolver finds an existing package by `metadata.sheet_id` / `scene_layout_id`, or builds a **non-destructive runtime package**. Never regenerates ERS because lookup failed. UI never asks for a package UUID. |
| Shared core | [`useSceneCreator.ts`](../../../studio-web/src/components/CoDirector/SceneCreator/useSceneCreator.ts) + [`SceneCreatorCore.tsx`](../../../studio-web/src/components/CoDirector/SceneCreator/SceneCreatorCore.tsx) |
| Scene ≠ Shot ≠ Candidate | `SceneShot` owns candidates. Four looks do not create four shots. |
| Take Law | `SceneShotTakeMemory` uses Timeline field names. Re-Take is a correction delta. Take A stays until Take B is approved. Generate after approve is refused. |
| Express light | Environment, Characters/Props, Camera, Shot Prompt, Generator, Generate, Candidates, Approve, Re-Take, Send to Timeline |
| Standard production tool | Left Scene/Shot browser, center preview, bottom take strip, right inspector |
| Generator law | Local checkbox. **API Generation — Not Available** (hosted image workflows are Blocked). API ON never routes through local Comfy. |
| Camera | Spatial Map WHERE + cinematic HOW. No silent Spatial writes. |
| Approved media | Only an approved take sets Library approval and can Send to Timeline |
| Timeline `sceneId` | `ensure_scene_id` binds a Studio Scene row. Empty `scene_id` is rejected. |
| Production menu | Scene Creator in. Scene Master Sheet and Continuity out of navigation. Backends kept. |

---

## Verifier history

1. First pass **REJECTED**: Express had no Re-Take (`RetakeBlock` was Standard-only). Generate after approve would replace candidates.
2. Repair: Express mounts Re-Take after approve; Generate is disabled and the API refuses; `retake_shot` appends candidates and keeps `approved_candidate_id`; Re-Take persists current camera/intent first.
3. Second pass **READY FOR MANUAL BETA**. No remaining Manual Beta blockers.

---

## Tests

- `studio-api/tests/test_scene_creator_express.py` — **16 passed**
- `studio-web` vitest `sceneCreatorContracts.test.ts` — **5 passed**
- `npm --prefix studio-web run build` — **passed** (`tsc -b && vite build`)

No Playwright (out of scope).

---

## Beta

This machine: creator UI **http://127.0.0.1:8760/** proxies Studio API **http://127.0.0.1:8761/**.

Hard-refresh the browser before Manual Beta.

Health observed after refresh:

- `http://127.0.0.1:8760/__beta_web_health` → 200
- `http://127.0.0.1:8761/api/health` → 200

Production Scene Creator is mounted from `ProjectEditor` for `scenecreator` and legacy `mastersheet`. Hard-refresh after this build.

Official `:8758` is not the live overlay on this machine.

---

## Manual Beta

### Express (Co-Director → Scene Creator)

A. Empty project without ERS shows Open Spatial Map + Choose Existing ERS.  
B. Choose Existing lists sheets when they exist (Environment select after a sheet is present).  
C. Selecting a sheet does not regenerate ERS.  
D. Characters/props chips come from Spatial Map.  
E. Camera: Default Camera or C1–C4 WHERE + Medium Wide / Static / Two Shot HOW.  
F. Local off → Generate disabled / zero local jobs.  
G. API shows Not Available. Enabling API must not run Comfy.  
H. Generate produces four candidates for **one** shot.  
I. Progress is honest.  
J. Use This Look approves one take.  
K. Send to Timeline disabled until approved.  
L. Approved take appears as approved in Library.  
M. Re-Take with a correction keeps Take A until Take B is approved. Generate stays disabled.  
N. Reload restores the shot.  
O. Spatial Map placements are unchanged.

### Standard (Production → Scene Creator)

A. Menu shows Scene Creator, not Scene Master Sheet or Continuity.  
B. Left Scene/Shot browser.  
C. Center preview of approved take.  
D. Bottom take strip.  
E. Right inspector has Environment, Characters & Props, Camera, Shot, Generation, Re-Take.  
F. Same shot as Express (shared core).  
G. Send to Timeline lands on a real Scene row.

---

## Limitations

- Hosted image generation is not Certified/executable. API control is honestly unavailable.
- Character Creator Cloud checkbox defect is **not** copied and **not** repaired in Character Creator (out of scope).
- Scene Master Sheet and Continuity workspaces still exist if opened by old links; Continuity is menu-hidden; Master Sheet URLs resolve to Scene Creator.
- Unrelated Production “models missing” copy was not changed.
- Standard inspector has no separate Advanced accordion (advanced camera HOW lives on the inspector Camera block).
- Default Camera (no N/E/S/W) may compile without an ERS directional still; Spatial C1–C4 with orientation attaches refs.
- Empty-state Choose Existing only appears when `listSheets` is empty; once sheets exist, the Environment dropdown is the chooser.

---

## Remaining

Manual Beta A–O / A–G. Then re-issue **GO** or keep **NO-GO** with the exact blocker.
