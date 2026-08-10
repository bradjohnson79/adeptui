# Adept UI Contrast Pairs (WCAG AA)

Authority: `docs/design/ADEPT_UI_DESIGN_SYSTEM.md`  
Tokens: `studio-web/src/theme/tokens.css`

Approved foreground / background combinations for Aurora dark:

| Foreground | Background | Use | Target |
|---|---|---|---|
| `--ink` (#f3f7fb) | `--bg1` (#070b14) | Body on canvas | AAA |
| `--ink` | `--panel-solid` | Body on panels | AA+ |
| `--ink` | `--panel-elevated` | Menus / dialogs | AA+ |
| `--muted` (#9db0c3) | `--bg1` / `--panel-solid` | Secondary text | AA |
| `--btn-primary-fg` (#06201c) | `--accent` (#2dd4bf) | Primary button label | AA+ |
| `--ink` | `--btn-bg` (`--panel-solid`) | Secondary button | AA |
| `--status-danger` | `--panel-solid` | Error labels | AA (large) / verify |
| `--aurora-gold` / `--warn` | `--panel-solid` | Warnings | AA (large) |

Forbidden:
- Dark text (`#151a1f` etc.) on `--bg0` / `--panel`
- Light gray text on white / near-white cards
- White cards with `--ink` assumed “dark mode” without checking

When adding a surface, pick from this table or update this file with measured ratios.
