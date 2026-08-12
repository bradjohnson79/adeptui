# M40 — Global UI Audit Punch List

| Field | Value |
|---|---|
| **Phase** | 4.0.1 |
| **Authority** | [`docs/design/ADEPT_UI_DESIGN_SYSTEM.md`](../../design/ADEPT_UI_DESIGN_SYSTEM.md) |
| **Date** | 2026-07-28 |
| **Scope** | Read-only scoring of every route + project workspace |

Scoring: **PASS** · **PARTIAL** · **FAIL** · **N/A**

---

## Global chrome & theme

| ID | Finding | Severity | Status |
|---|---|---|---|
| G-01 | Dual button systems (`button.primary` vs `ui-btn`) | High | FAIL |
| G-02 | Light/white `.card` / `.dash-card` / setup dialogs on Aurora dark | High | FAIL |
| G-03 | Token triplication (`styles.css`, `aurora-theme.css`, `aurora-landing.css`) | High | FAIL |
| G-04 | Nav duplication: StudioChrome links + hamburger + ProjectHome cards + CoDirectorNavDrawer | High | FAIL |
| G-05 | No desktop menu bar / toolbar; cluttered horiz nav | High | FAIL |
| G-06 | Header search shows ⌘K but no command palette | Medium | FAIL |
| G-07 | Missing dashboard JPGs; gradients used as primary card media | High | FAIL |
| G-08 | Director shell fixed columns; no SplitPane | Medium | FAIL |
| G-09 | Co-Director resize handle CSS unused | Medium | PARTIAL |
| G-10 | Satellite pages (Model Radar, Production Suite) lack StudioChrome | Medium | FAIL |
| G-11 | Orphan CSS: `index.css`, `App.css`, unused `m214-unified.css` | Low | FAIL |
| G-12 | Thin empty states (“No projects”) without artwork + CTA pattern | Medium | FAIL |
| G-13 | Hardcoded hex in feature CSS / inline styles | High | FAIL |
| G-14 | Workspace hamburger not driven by `WORKSPACES` registry | High | FAIL |
| G-15 | URL `?workspace=` not synced on tab change | Medium | FAIL |
| G-16 | No named saved layouts | Medium | FAIL |
| G-17 | Motion not standardized to 100–250 ms Design Language | Low | PARTIAL |
| G-18 | Contrast: muted-on-glass generally OK; light cards create invisible/low-contrast text risk | High | FAIL |

---

## Routes (`App.tsx`)

| Route | Spacing | Type | Contrast | Nav | Empty | Motion | Notes |
|---|---|---|---|---|---|---|---|
| `/` Home | PARTIAL | PARTIAL | PARTIAL | FAIL | FAIL | PARTIAL | Aurora landing strong; cards thin; chrome clutter |
| `/project/:id` | PARTIAL | PARTIAL | PARTIAL | FAIL | PARTIAL | PARTIAL | Hamburger mega-menu; fixed director grid |
| `/co-director` | PARTIAL | PASS | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Needs distinct assistant density polish |
| `/source-manager` | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Uses StudioChrome; status duplication |
| `/model-radar` | FAIL | PARTIAL | PARTIAL | FAIL | PARTIAL | N/A | Minimal header |
| `/production-suite` | FAIL | PARTIAL | PARTIAL | FAIL | PARTIAL | N/A | Minimal header |
| `/virtual-stage` | PASS | PASS | PASS | PARTIAL | N/A | N/A | Deferred page |
| `/environment-studio` | PASS | PASS | PASS | PARTIAL | N/A | N/A | Deferred page |

---

## Project workspaces (`workspaces.ts`)

| Workspace | Buttons | Forms | Cards/Panels | Empty | Contrast | Notes |
|---|---|---|---|---|---|---|
| home | PARTIAL | N/A | PARTIAL | PARTIAL | PARTIAL | Explore cards need rich anatomy |
| setup | FAIL | PARTIAL | FAIL | PARTIAL | FAIL | Light dialogs / cards |
| settings | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| imagegen | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| one | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Director shell |
| txt2vid | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| three | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Director shell |
| director | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Fixed 3-pane |
| profiles | PARTIAL | PARTIAL | PARTIAL | FAIL | PARTIAL | |
| tools | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Legacy |
| spatial | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| script | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| shotlist | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Legacy |
| generate | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Legacy |
| library | PARTIAL | PARTIAL | PARTIAL | FAIL | PARTIAL | |
| marketplace | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| mastersheet | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| avatar | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| characters | PARTIAL | PARTIAL | PARTIAL | FAIL | PARTIAL | Needs rich empty state |
| bible | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| editor | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| audiostudio | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | Inline styles hotspot |
| generationtools | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| scriptwriter | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |
| brandstudio | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | |

---

## Design Language gap map → Phase 4.0 work

| Design Language chapter | Gap | Owned by |
|---|---|---|
| Colors / no local colors | Tokens triplicated; hex drift | 4.0.2–4.0.3 |
| Typography | Scale classes incomplete | 4.0.2 |
| Menus | No desktop menu bar; registry unused for menus | 4.0.4 |
| Toolbar + Quick Search | Missing | 4.0.5 |
| SplitPane + layouts | Missing | 4.0.6 |
| Artwork library + rich cards | Missing files / thin cards | 4.0.7 |
| Navigation | Duplicated | 4.0.8 |
| Co-Director shell | Not assistant-distinct enough | 4.0.9 |
| Empty states / motion | Thin / unstandardized | 4.0.10 |
| Validation / cert | Pending | 4.0.11–4.0.12 |

---

## Exit for 4.0.1

Punch list complete. Implementation begins at 4.0.2 against this list and the Design Language.
