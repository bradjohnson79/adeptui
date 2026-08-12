# Qwen2512 Character Creator UI Handoff

## Scope completed

- Switched Character Creator visual-sheet generation in `studio-api/app/character_identity/visual_sheet.py` to a pure `qwen2512.txt2img` path for hero, coverage, details, and performance phases.
- Replaced the old mixed-engine `zimage.ref_edit` behavior with Method B sequential `qwen2512.txt2img` jobs driven by compiled identity prompts.
- Updated Character Creator UI copy in `studio-web/src/components/CharacterProfileWorkspace.tsx` so Qwen-Image-2512 is the recommended visual-sheet default.
- Updated Co-Director tool preview wording in `studio-api/app/codirector/tools/handlers/character_creator.py` to describe the real engine path honestly.

## How prompts are compiled now

Character Creator no longer sends loose prose for the Korri visual-sheet path.

For every hero/coverage/detail/performance image job, `visual_sheet.py` now calls:

- `app.image_prompting.qwen_2512.compile_character_image_prompt(...)`

The helper builds a structured 13-block Qwen prompt package from the live Character Profile payload:

- profile identity fields
- hair / skin / motion / performance fields
- active wardrobe when present
- attached Character Identity references
- per-role composition instructions
- per-role sheet view mapping for turnaround and close-up coverage

The queued job uses:

- `prompt = package.prompt`
- `negative_prompt = package.negative_prompt`
- `modelFamilyPreference = "qwen2512"`
- `creativeContext.workflowKey = "qwen2512.txt2img"`

## `ref_edit` status

`ref_edit` was replaced for this cert path.

- Previous state: pack metadata and follow-up jobs still implied `zimage.ref_edit`.
- New state: pack metadata is explicit that the Character Creator visual-sheet flow is sequential `qwen2512.txt2img`.
- Result: no silent engine mixing on the Korri certification path.

## Primary Korri live-run payloads

Saved machine-readable payload examples in:

- `artifacts/m42/w43-qwen-2512/character-creator/korri-live-run-request-payloads.json`

Key API calls:

```json
POST /api/projects/{projectId}/characters/{characterId}/visual-sheet/start
{
  "includeDetails": true,
  "includePerformance": true
}
```

```json
POST /api/projects/{projectId}/characters/{characterId}/visual-sheet/advance
{}
```

```json
POST /api/projects/{projectId}/characters/{characterId}/visual-sheet/owner-approve
{
  "approvedBy": "owner"
}
```

Expected pack metadata after start/advance:

```json
{
  "engine": "qwen2512.txt2img",
  "workflows": [
    "qwen2512.txt2img",
    "character_sheet",
    "sequential_identity_prompts",
    "coverage_pack",
    "detail_pack",
    "performance_pack"
  ],
  "referenceEditReplaced": true
}
```

## Next steps for the primary Korri live run

1. Use the existing Korri Character Profile inside the open project. Do not create a new project.
2. Start the visual sheet with `includeDetails=true` and `includePerformance=true`.
3. Advance until the pack reports `READY_FOR_OWNER`.
4. Verify the first hero and coverage outputs against Korri lock requirements:
   black twin ponytails, purple eyes, pale skin, pointed Sun Sprite Elf ears, wooden accessories, light-circuitry markings, handmade black wardrobe.
5. Owner-approve only after all required coverage roles are attached and visually correct.
6. Save any live-run evidence alongside the existing `artifacts/m42/w43-qwen-2512/character-creator/` bundle.

## Notes for the next owner

- The Character Creator UI now recommends Qwen-Image-2512 for visual sheets, but this change does not alter FLUX availability elsewhere.
- The visual-sheet flow still waits for a hero asset before coverage proceeds, but follow-up phases now stay on the same Qwen txt2img engine path instead of switching to reference edit.
