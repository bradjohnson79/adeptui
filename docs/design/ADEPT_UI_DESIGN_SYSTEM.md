# Adept UI Design System (Law of the Project)

| Field | Value |
|---|---|
| **Phase** | 4.0.0 — Adept UI Design Language |
| **Status** | Authoritative |
| **Theme** | Aurora Night (default) + Aurora Day (authorized dual theme) |
| **Identity** | DaVinci Resolve meets the Northern Lights |
| **Code tokens** | `studio-web/src/theme/tokens.css` |
| **Components** | `studio-web/src/components/ui/` (Design System) |

This document is the **law of the project**. New workspaces, cards, dialogs, and tools must inherit from this system. Do not invent new colors, type scales, card layouts, or motion patterns.

**Philosophy:** Adept UI should look and behave like a premium desktop creative application first, and a web application second. Every interface decision favors clarity, consistency, discoverability, and efficient creative workflows.

**Refine, do not redesign.** Preserve the cinematic Aurora hero, glass panels, and teal/cyan/violet language.

**Themes (M42 Production Dock amendment):** Components must use semantic tokens (`--surface-primary`, `--text-primary`, `--border-default`, `--accent-primary`, `--field-background`, etc.). Aurora Night remains the default. Aurora Day is a real light theme (pale blue/pearl surfaces, dark navy text, stronger shadows, reduced glow) — never a simple color inversion. Follow System resolves to Night or Day from OS preference.

---

## 1. Identity

- **Brand surface:** Deep navy canvas with soft aurora washes (teal, cyan, violet).
- **Feel:** Immersive cinematic suite — not a flat corporate web app.
- **Reference apps:** DaVinci Resolve, Adobe Creative Cloud, Affinity, Blender, Unreal — for density and chrome; Aurora for color and atmosphere.
- **Co-Director exception:** Distinct AI-assistant shell (large chat, minimal clutter, side context). Still token-driven.

---

## 2. Colors

All color literals live **only** in `studio-web/src/theme/tokens.css`.  
**Rule: No component or feature stylesheet may define its own colors.** Use `var(--*)` exclusively. No exceptions.

### Surfaces

| Token | Role |
|---|---|
| `--bg0` | Deepest canvas |
| `--bg1` | App background |
| `--panel` | Glass panel |
| `--panel-solid` | Opaque panel / elevated control |
| `--panel-elevated` | Raised surfaces (menus, dialogs) |
| `--line` / `--border-glass` | Soft cyan-tinted borders |

### Brand accents

| Token | Role |
|---|---|
| `--aurora-teal` / `--accent` | Primary (Adept teal) |
| `--aurora-violet` | Secondary |
| `--aurora-gold` | Accent / highlight (sparing) |
| `--aurora-cyan` / `--aurora-blue` | Information / links |
| `--aurora-green` / `--accent-soft` | Soft success / glow |

### Semantic

| Token | Role |
|---|---|
| `--ok` / `--status-positive` | Success |
| `--warn` / `--status-warning` / `--aurora-gold` | Warning |
| `--danger` / `--status-danger` | Error |
| `--status-info` | Information |
| `--status-muted` / `--disabled` | Disabled / muted |

### Text

| Token | Role |
|---|---|
| `--ink` | Primary text on dark surfaces |
| `--muted` | Secondary text |
| `--disabled` | Disabled text |

### Contrast law

- Never white text on white / near-white surfaces.
- Never dark charcoal text on dark navy panels.
- Body text on `--panel-solid` / `--bg1` must meet **WCAG AA** (≥ 4.5:1 for normal text).
- See `studio-web/src/theme/contrast.md` for approved pairs.
- No light “paper” cards on Aurora canvas — cards use dark glass tokens.

---

## 3. Typography

| Token / class | Use |
|---|---|
| `--font-display` (Fraunces) | Brand, hero titles, workspace titles |
| `--font-body` (Manrope) | UI, body, labels, menus |

### Scale

| Role | Class | Guidance |
|---|---|---|
| Display | `.ds-type-display` | Hero / landing only |
| H1 | `.ds-type-h1` | Page title |
| H2 | `.ds-type-h2` | Section |
| H3 | `.ds-type-h3` | Card / panel title |
| Body | `.ds-type-body` | Default |
| Label | `.ds-type-label` | Form labels, menu items |
| Helper | `.ds-type-helper` | Hints, captions (`--muted`) |
| Mono | `.ds-type-mono` | IDs, paths, code |

Do not introduce alternate display fonts for marketing flair inside the app shell.

---

## 4. Spacing

| Token | Value |
|---|---|
| `--space-1` | 0.25rem |
| `--space-2` | 0.5rem |
| `--space-3` | 0.75rem |
| `--space-4` | 1rem |
| `--space-5` | 1.5rem |
| `--space-6` | 2rem |
| `--space-8` | 3rem |

Use the scale for padding/gaps. Prefer `--space-4` / `--space-5` for panel padding. Avoid one-off pixel spacing except for hairline borders (1px).

---

## 5. Border radius

| Token | Use |
|---|---|
| `--radius-control` | Buttons, inputs, selects |
| `--radius` | Cards, large panels |
| `--radius-chip` | Pills / chips |
| `--radius-menu` | Menus / popovers |

---

## 6. Shadows and glow

| Token | Use |
|---|---|
| `--shadow` | Default elevation |
| `--shadow-lift` | Menus, dialogs, lifted cards |
| `--glow-cyan` / `--glow-violet` | Restrained focus / hero accents only |

Glow is atmospheric, not neon spam. Prefer borders + soft shadow for interactive chrome.

---

## 7. Icons

- Toolbar icons: 18–20px optical size, consistent stroke.
- Menu icons: optional, 16px; text labels required.
- Always provide `aria-label` on icon-only controls.
- Prefer simple geometric SVGs from `public/images/ui/icons/` or inline SVG using `currentColor`.

---

## 8. Buttons

Use Design System `Button` / `IconButton` only (`ui-btn`).

| Variant | Use |
|---|---|
| `primary` | One primary action per region |
| `secondary` | Default actions |
| `tertiary` / `ghost` | Low emphasis |
| `danger` | Destructive |
| `icon` | Toolbar |

States: default, hover, active/selected, disabled, loading. Focus via `--focus-ring`.

Do not use raw `<button class="primary">` in new code.

---

## 9. Menus

### Desktop menu bar

Top application chrome:

`File · Edit · Project · Generate · Characters · Production · Tools · Window · Settings · Help`

- Cascading menus; keyboard (Alt, arrows, Escape).
- **Workspace items are generated from the Workspace Registry** (`menuGroup`, `order`). New workspaces appear automatically.
- File / Edit / Settings / Help remain static app actions.

### Context menus

Same visual language as cascading menus (`--panel-elevated`, `--shadow-lift`).

---

## 10. Toolbar

Secondary bar under the menu:

New · Open · Save · Undo · Redo · Generate · Render · Co-Director · Character Creator · Production Bible · Project Library · **Quick Search**

Icon-first with tooltips. Disabled when context missing.

---

## 11. Quick Search

Blender-style command palette:

- Shortcuts: `Ctrl+K` / `Ctrl+Space` (Mac: `Meta+K`; avoid stealing OS Spotlight).
- Indexes workspaces (registry), tools, recent projects.
- Fuzzy filter; Enter runs; Esc closes.

---

## 12. Cards

### Rich workspace / dashboard card

Required anatomy:

1. Beautiful local artwork (`public/images/ui/…`)
2. Workspace title (display/H3)
3. Short description
4. Capability badges
5. `Open →` affordance

Photo first; Aurora plate CSS only as `onError` fallback. No placeholder-only gradients as the intended final look.

### Surfaces

Cards use dark glass (`--panel` / `--panel-solid`), not white paper.

---

## 13. Dialogs

- Backdrop dim + elevated panel (`--panel-elevated`).
- Title, body, primary + secondary actions.
- Confirm destructive actions explicitly.
- Esc / click-outside per dialog policy; focus trap required.

---

## 14. Forms, tables, tabs, panels, inspectors

- Forms: `FormField` + tokenized inputs.
- Tables: Design System `DataTable`.
- Tabs: Design System `Tabs`.
- Panels / inspectors: glass panels with `--space-4` padding; collapsible via SplitPane / Window menu.
- No one-off “settings box” styles.

---

## 15. Empty states

Never a bare “No items” string.

Required:

1. Artwork from `public/images/ui/empty-states/` (or plate fallback)
2. Clear title
3. Helpful explanation
4. Primary CTA button

Example: **No Characters Yet** — Create your first character profile. `[ Create Character ]`

---

## 16. Animations

- Duration: **100–250 ms**
- Easing: standard ease / ease-out
- Allowed: opacity, transform (subtle), panel width, menu open
- Banned: bounce, large fades, attention-seeking loops, flashy parallax
- Existing subtle aurora canvas drift may remain; do not add new decorative loops to UI chrome

Tokens: `--motion-fast` (100ms), `--motion-base` (160ms), `--motion-slow` (250ms).

---

## 17. Responsive behavior

- Fluid layouts from laptop (~1366×768) to 4K / ultrawide.
- `SplitPane`: drag resize, minimum widths, collapse.
- Named saved layouts (localStorage): Editing, Writing, Generation, Audio.
- Soft-stack inspectors below ~1280px; preserve cinematic monitor priority.
- No overlapping or clipped content at certified viewports.
- Workspace selection syncs to `?workspace=` URL.

---

## 18. Co-Director assistant shell

Must feel like a dedicated AI assistant (Agent One / ChatGPT Desktop / Claude / Gemini Canvas):

- Large chat as the hero region
- Minimal clutter; no dense studio nav inside the overlay
- Project context on a resizable side panel
- Aurora glass + restrained glow + excellent typography
- Specialized cinematic skin is allowed; **still token-driven**

---

## 19. Artwork library

All UI imagery is local:

```
studio-web/public/images/ui/
  dashboard/
  workspaces/
  templates/
  cards/
  hero/
  backgrounds/
  empty-states/
  placeholders/
  icons/
LICENSE.md
```

- Original, royalty-free, or AI-generated with verified commercial usage.
- No runtime external image URLs.
- License notes in `LICENSE.md`.

---

## 20. Contribution rule (maturity test)

A new developer must be able to create an entirely new workspace using **only** Design System components and Workspace Registry registration, **without inventing any new CSS or UI patterns**.

Checklist for a new workspace:

1. Register in `workspaces.ts` (`menuGroup`, `order`, badges, `commandPalette`).
2. Compose UI from Design System primitives.
3. Use tokens only for any layout CSS (no color literals).
4. Provide rich empty state + optional card artwork under `public/images/ui/`.
5. Appear automatically in Menu · Quick Search · cards.

---

## 21. Anti-patterns (forbidden)

- Hardcoded hex/rgb in feature CSS
- White cards on Aurora dark
- Duplicate navigation systems (hardcoded hamburgers that ignore the registry)
- Flashy motion (>250 ms decorative)
- Thin empty states without CTA
- Light theme toggles in v1.1
- Parallel “mini design systems” inside feature folders

---

## Related files

| Artifact | Path |
|---|---|
| Tokens | `studio-web/src/theme/tokens.css` |
| Typography | `studio-web/src/theme/typography.css` |
| Contrast pairs | `studio-web/src/theme/contrast.md` |
| Design System components | `studio-web/src/components/ui/` |
| Re-export barrel | `studio-web/src/components/design-system/index.ts` |
| Workspace registry | `studio-web/src/core/workspaces.ts` |
| Phase 4.0 audit | `docs/release-gate/m40/M40_UI_AUDIT_PUNCHLIST.md` |
| Phase 4.0 cert | `docs/release-gate/m40/M40_UI_CERTIFICATION_REPORT.md` |
| Systems audit pointer | `docs/ADEPT_UI_SYSTEMS_AUDIT.md` |
