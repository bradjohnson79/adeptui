# PROP CREATOR EXPRESS — COMPLETION REPORT

**Date:** 2026-08-14  
**Branch:** `beta`  
**Starting SHA:** `756bfd9f3592f99a2e4e2e0910bf3686c4dabdba`  
**Governing audit:** [`PROP_CREATOR_EXPRESS_AUDIT.md`](./PROP_CREATOR_EXPRESS_AUDIT.md)  
**Independent verifier:** [Re-verify Prop Creator](05983b27-60d2-4219-ba3b-7ca4ec0a29e0) — first pass **REJECTED** (Scene Creator shot bind missing); repair; second pass **READY FOR PRIMARY REVIEW**

Playwright is out of scope. Automated gate: **READY FOR MANUAL BETA**. Do not treat that as product GO.

---

## Verdict

**READY FOR MANUAL BETA**

Implementation, automated tests, production build, Beta refresh, and independent verification are complete. Product GO requires creator Manual Beta A–N.

---

## What shipped

Project props are extended `PropEntity` records. No second registry. Character Creator Props & Accessories (`character_props`) is unchanged and is a different product.

| Law | Implementation |
|---|---|
| Identity | `PropEntity.id` is `propId`. `approved_asset_id` is canonical visual. `library_asset_id` mirrors approved only after **Use This Prop**. |
| Drafts | Name / style / description / optional reference save without generation or approval. |
| Generation modes | Reference-capable families are **Reference Conditioned**. Illustrious XL / Qwen stay available as **Description Guided**. Pixels attach only on the conditioned path. |
| Compiler | One `compile_prop_prompt`. Identity stills: centered complete prop, not a held-prop scene or four-view sheet. |
| Reference vs approved | `clear_reference` unlinks `reference_asset_id` only. |
| Spatial Map | Approved project props first, then character props, then tagged Library. Project props bind `propId` + approved visual. Library items keep `propId: null`. |
| Scene Creator | Placed approved `PropEntity` ids are unioned onto the shot before generate. Prompt gets name + description. Approved visual is a reference image. |
| Honesty | Local OFF = zero local jobs. API OFF = zero API jobs. API ON without a hosted path = **API Generation — Not Available**. `generate_character_prop` is not used. |
| Express | `usePropCreator` + `PropCreatorCore`. Co-Director tab after Character Creator. No Standard workspace now. |

---

## Verifier history

1. First pass **REJECTED**: Scene Creator chips were display-only; `prop_entity_ids` stayed empty on a new shot, so generate omitted approved identity.
2. Repair: `_ensure_placed_project_props` unions placed approved PropEntity ids onto the shot; Express chips toggle; `useSceneCreator` seeds from `workspace.props[].prop_id`.
3. Second pass **READY FOR PRIMARY REVIEW**. No remaining automated Law 7 blocker.

---

## Tests

- `studio-api/tests/test_prop_creator_express.py` — **12 passed**
- `studio-api/tests/test_scene_creator_express.py` — **16 passed** (regression)
- `studio-web` vitest Prop Creator + Scene Creator contracts — **11 passed** (5 Prop Creator + 6 Scene Creator)
- `npm --prefix studio-web run build` — **passed** (`tsc -b && vite build`)

No Playwright (out of scope).

---

## Beta

This machine: creator UI **http://127.0.0.1:8760/** proxies Studio API **http://127.0.0.1:8761/**.

Hard-refresh the browser before Manual Beta.

Health observed after refresh:

- `http://127.0.0.1:8760/__beta_web_health` → 200
- `http://127.0.0.1:8761/api/health` → 200
- `GET /api/prop-creator/projects/missing/workspace` → 404 (router mounted; project missing)

Official `:8758` is not the live overlay on this machine. ComfyUI on `:8188` was left running.

---

## Manual Beta

Hard-refresh **http://127.0.0.1:8760/**. Open an existing project. Co-Director → **Prop Creator** (tab after Character Creator).

### Express A–K

A. Tab is next to Character Creator.  
B. **Create New**. Name stays blank (never “New Prop”).  
C. Name, Image Style, Description. **Save**. Reload still shows the draft.  
D. **Add from Library** (or Upload). Thumbnail appears.  
E. Remove reference. Approved identity, if any, stays.  
F. Local generator on, Auto Select. **Generate Prop Images**.  
G. Progress shows `n of 4 complete`. Failed card has **Retry**. No infinite spinner.  
H. Four looks. **Use This Prop** on one.  
I. Save. Reload. That look is still the Prop identity.  
J. API row reads **API Generation — Not Available**. Unchecked Local does not start jobs.  
K. Delete warns about Spatial Map unlink. Library images remain.

### Spatial Map / Scene Creator L–N

L. Spatial Map Saved Prop lists the **approved** project prop first (drafts are absent).  
M. Select + Place. Placement keeps `propId` (not a generic Library item).  
N. Scene Creator shows the prop chip and generation can use the approved still + description.

---

## Limitations

- Hosted image generation is not Certified/executable. API control is honestly unavailable.
- Character Creator Cloud checkbox defect is not copied and not repaired.
- Character props are not auto-converted into project props.
- Generate unions placed approved project props onto the shot even if a Scene Creator chip was toggled off (Law 7: placed props must reach the shot).
- Express only. Standard Prop Creator is not built.
- Playwright not run.

---

## Remaining

Manual Beta A–N. Then re-issue **GO** or keep **NO-GO** with the exact blocker.
