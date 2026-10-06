# Brand Studio — Adept UI v1.1 retirement

**Governing note for Adept UI v1.1.** Historical Brand Studio reports remain historical.

Brand Studio is **retired from Adept UI v1.1**. It is no longer a product surface, route, menu item, capability, or generation tool.

Reconsider for **Adept UI v1.2** as a separately scoped product rather than restoring the legacy implementation automatically.

## Why

v1.1 is centered on creation, scene production, audio, Timeline, and Co-Director. Brand Studio was a campaign/identity studio that pulled that focus. Hiding it while leaving it mounted would have left a live, chargeable path.

## Active product (removed)

- Home Explore card `brandstudio`
- Production menu → Creative Studios → Brand Studio
- `?workspace=brandstudio` (and aliases `brand`, `branding`, `promo`)
- ProjectEditor mount of `BrandStudioWorkspace`
- Generation Tools catalog `brand.studio` and hub “Open Brand Studio”
- Co-Director mutation `propose_brand_generate`
- Tests that certified Brand Studio as current v1.1 behavior

Stale `?workspace=brandstudio` deep links resolve to **Project Home** on the same project. They must not remount Brand Studio.

## Intentionally preserved

| Kind | What | Why |
|---|---|---|
| Dormant project data | `settings_json.brandStudio` | v1.2 migration path; do not delete |
| Dormant asset provenance | `op=brand_generate`, `brandStudio`, `m32aBrand` | Historical jobs |
| Archived source | `legacy/adept-ui-v1.1-retired/brand-studio/` | Reference only; not imported |
| Brand Ad project type | `brand_ad` template / project trait | Commercial production shape, not Brand Studio |
| Shared generation tools | Upscale, chroma, audio, lineage | Other workspaces depend on them |
| Plan compatibility | deferred prefix `propose_brand` | Old plans stay non-executable |

## Do not

- Re-add `brandstudio` to `WORKSPACES`, Explore, or Production menu
- Re-register `brand.studio` or `propose_brand_generate`
- Import archived frontend/backend from `legacy/`
- Treat “Brand Ad” template retirement as the same change
- Destructively wipe `settings_json.brandStudio` rows
