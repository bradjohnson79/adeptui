# M3.2e — Aurora Theme Report

## Summary

Application-wide Aurora cinematic dark theme is promoted from Home-scoped `.aurora-landing` into global semantic tokens. Director, Source Manager, Tools Hub, and chrome inherit dark glass surfaces. Co-Director cinematic shell remains quarantined (token aliases only).

## Changes

- Global tokens remapped in `studio-web/src/styles.css` and reinforced by `studio-web/src/theme/aurora-theme.css`
- Body / atmosphere / topbar / panels / workspace tabs flipped to dark Aurora
- Status tone tokens (`--status-*`) and media-monitor neutrality (`--media-monitor-bg`)
- Co-Director `--codirector-*` aliased to Aurora surfaces
- Scrollbars: thin dark track + aurora thumb

## Validation

- Playwright: `tests/e2e/m32e/aurora-theme.spec.ts` (M32E-THEME-01..22) — **passed**
- Full M32E suite (theme + IA): **47 passed**
- Regression: GENSTUDIO-UI + CODIRECTOR-UI — **38 passed**
- Screenshots: `artifacts/m32/aurora-theme/`
- Inventory: `artifacts/m32/aurora-theme/theme-inventory.md`

## Non-goals preserved

- No runtime AI card imagery
- No Co-Director layout rewrite
- Media preview panes stay neutral dark (no aurora gradients over video)
