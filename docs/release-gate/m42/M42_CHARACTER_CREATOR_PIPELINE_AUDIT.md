# M42 Character Creator Pipeline Audit

**Sprint:** Character Creator Correction — Korri Identity Lock  
**Date:** 2026-07-31  
**Mock data:** false  
**Live evidence project:** `040dc342-3186-4eeb-9a52-4b7e8e43ff9a`  
**Character:** `e05ceeea-0f13-4797-acb7-0eb7bc86c19c` (Korri)

---

## Verdict (pipeline map)

Every stage below was exercised live through Adept UI Beta API → in-process QueueWorker → ComfyUI `8188` → Asset Library → Visual Sheet pack → Owner approve.

```text
Character Creator UI / API
        ↓
Identity Registry (seed-korri ← korri.v1.json)
        ↓
Prompt Builder (prompt_package + KORRI_LOCK + role suffixes)
        ↓
Workflow Builder (zimage.txt2img | zimage.ref_edit)
        ↓
ComfyUI queue + execution
        ↓
Generation + output fetch
        ↓
Validation (output_gate) + Asset commit
        ↓
Character Sheet pack (roleAssets + visual gates)
        ↓
Asset Library + character_reference_assets
        ↓
Asset version / parent linkage (ref_edit)
        ↓
Owner approve → OWNER_APPROVED
```

---

## Stage inventory

| Stage | Primary code | Status |
|---|---|---|
| Character Creator UI | `studio-web/src/components/CharacterProfileWorkspace.tsx`, `TimelineCharacterCreatorPanel.tsx` | Wired |
| Seed / Canon | `config/character-canon/korri.v1.json`, `character_identity/service.seed_korri_from_canon` | Wired |
| Prompt Builder | `character_identity/prompt_package.py`, `visual_sheet._identity_prompt`, `_coverage_role_prompts` | Wired |
| Workflow Builder | `workflows/image_tools.build_zimage_txt2img_workflow`, `build_zimage_ref_workflow` | Wired + corrected |
| Contract / drift gate | `image_runtime/workflow_execute.prepare_executable_graph`, `certified-registry.json` | Wired + re-fingerprinted |
| Queue / Comfy | `queue_worker._imagegen`, `comfy_client` | Wired |
| Asset registration | `_imagegen_commit_asset`, `character_identity.service.attach_reference` | Wired |
| Visual sheet FSM | `character_identity/visual_sheet.py` | Wired |
| Owner approve | `owner_approve_visual_sheet_gates` | Wired |
| Persistence | trait `visual_sheet_pack` + project assets on disk | Verified (reload 15 roles) |

---

## Live pack phases (actual)

| Phase | Workflow | Roles |
|---|---|---|
| Hero | `zimage.txt2img` | `hero_portrait` |
| Coverage (`turnaround_facial`) | `zimage.txt2img` (`coverage_pack`) | 6 turnaround/closeup roles |
| Details | `zimage.ref_edit` (hero source) | 6 detail roles |
| Performance | `zimage.ref_edit` | `expression_sheet`, `pose_sheet` |
| Owner | gates → `OWNER_APPROVED` | all 5 gate groups |

**Note:** Coverage intentionally uses per-role txt2img (not the legacy multi-view `character_sheet` job kind). The `character_sheet` job still exists on the Image Tools path and now uses the fixed `zimage.ref_edit` graph.

---

## Evidence

- Cert: `artifacts/m42/w43/visual_sheet_results.json` (`passed: true`, 15 roles, `mock: false`)
- Sheets: `artifacts/m42/character-creator/korri-sheets/*.png`
- Workflows: `artifacts/m42/character-creator/workflow-zimage-*.json`
- Prompt package: `artifacts/m42/character-creator/prompt-package.json`
- Reload: `artifacts/m42/character-creator/visual-sheet-reload.json` (`OWNER_APPROVED`, 15 roles)

---

## Audit conclusion

The Character Creator → ComfyUI pipeline is fully mapped and was executed end-to-end without mock assets. Blocking platform failures found during this sprint were corrected (see Failure Analysis).
