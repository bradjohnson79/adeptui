# Image Generator — Prompt-Native Reference Tagging (PRIMARY REVIEW)

## Hard refresh (Brad)
1. Open Cinematic Image Generator for the project.
2. Hard refresh the Vite app: `Ctrl+Shift+R` (or DevTools → Network → Disable cache → reload).
3. Confirm Shot Description shows the **Active references** strip directly underneath.
4. Do **not** restart Comfy.

## What shipped
- Shared authority: dropdown catalogs == autocomplete == active chips == `referenceAssetIds`.
- Grammar: `@Character` `%Prop` `#Environment` `~GenericImage`; PoseCraft as `~PoseCraft_<SanitizedName>` (ONE).
- Environment ONE (replace). Characters/Props multi. Generic `~` multi capped at 8.
- Active References strip under Shot Description (click tag → insert at cursor; × removes).
- Autocomplete on `@ % # ~` with Up/Down/Enter/Tab/Escape + click.
- Manual tags resolve on blur + generate preflight; unresolved shows “Did you mean…”.
- Persist/reload via `localStorage` key `adept_image_generator_plan_<projectId>`; project switch re-scopes.
- Co-Director: `publishImageGeneratorPlanning` module store + chat body `imageGeneratorPlanning` (Env Creator pattern).

## Tests 1–9 (live prove)

| # | Action | Expect |
|---|--------|--------|
| 1 | Type `@` in Shot Description | Autocomplete opens from Character catalog |
| 2 | Pick `@Korri` from autocomplete | Tag inserted; Active strip shows Korri; `referenceAssetIds` debug line includes Korri asset |
| 3 | Add second `@` character | Both active (multi) |
| 4 | Select Environment A then Environment B | Only B active (replace); if prompt still has `#A`, warn |
| 5 | Select PoseCraft snapshot | Chip is `~PoseCraft_Name`; only one PoseCraft active |
| 6 | Library pick | Becomes `~` chip (or role-appropriate); no fifth Other dropdown |
| 7 | Type `@Nobody` then blur | Unresolved warning with Did you mean… |
| 8 | Generate with `@Korri` in prompt | Network/compile payload `referenceAssetIds` includes Korri (also visible in UI debug line) |
| 9 | Soft reload page | Prompt + active ref IDs/chips restore for same project; switch project clears/re-scopes |

### Payload prove
- UI: read `data-testid="cis-refids-debug"` under Shot Description.
- Network: Image Studio compile/generate request body → `referenceAssetIds`.

## Unit / Vite
```bash
npx vitest run src/components/image-studio/igPromptTokens.test.ts
npx vite build
```

## Files changed (core)
- `src/components/image-studio/igPromptTokens.ts` (+ test)
- `src/components/image-studio/cisAuthorityTypes.ts`
- `src/components/image-studio/imageGeneratorPlanning.ts`
- `src/components/image-studio/IgPromptNativeField.tsx`
- `src/components/image-studio/AuthorityReferencePanel.tsx`
- `src/components/image-studio/CinematicImageStudio.tsx`
- `src/components/image-studio/cinematic-image-studio.css`
- `src/components/CoDirector/CoDirectorSession.tsx`
- `src/i18n/locales/en/imageGenerator.json`
- `docs/IG_PROMPT_NATIVE_REFERENCE_TAGGING.md`
