# M3.2e — Aurora Imagery Report

## Strategy

Local SVG/CSS cinematic plates + typed registry. No runtime image generation. Owner photos can drop into `studio-web/public/images/dashboard/` without layout rewrites.

## Deliverables

- Registry: `studio-web/src/theme/auroraCardImagery.ts`
- Plates CSS: `studio-web/src/theme/aurora-plates.css`
- Card shell: `studio-web/src/components/ui/ImageReadyCard.tsx`
- `dashboardImages.ts` prefers Aurora registry paths + plate classes
- Template carousel / cards wire `image.plate` under media fallbacks

## Inventory

See `artifacts/m32/aurora-imagery/imagery-inventory.md`.

## Screenshots

`artifacts/m32/aurora-imagery/`
