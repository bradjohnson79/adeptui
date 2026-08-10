# Adept UI Artwork Library License

Path: `studio-web/public/images/ui/`

## Bundled assets

| Asset class | License | Notes |
|---|---|---|
| Cinematic template stills (`templates/*.jpg`) | Original Adept FilmWorks AI-generated artwork | Created for Adept UI product use; commercial use within the application granted (2026-07-28) |
| Create Project still (`cards/create-project-screenplay.jpg`) | Original Adept FilmWorks AI-generated artwork | Screenplay desk motif; commercial use within the application granted (2026-07-28) |
| Library cover motifs (`motifs/cover-*.svg`, `motifs/cover-screenplay.jpg`) | Original Adept FilmWorks artwork | Clapboard / camera / screenplay placeholders for project cards (2026-07-28) |
| Workspace explore stills (`workspaces/ws-*.jpg`) | Original Adept FilmWorks AI-generated artwork | Explore Adept UI card imagery; commercial use within the application granted (2026-07-28). Core creation expansion adds `ws-one-frame.jpg`, `ws-three-frame.jpg`, `ws-character-creator.jpg`, `ws-scriptwriter.jpg` (2026-08-04). |
| Cinematic SVG plates (`workspaces/`, `cards/`, `empty-states/`) | Original Adept FilmWorks artwork | Fallback plates; commercial use within the product granted |
| Hero imagery (`hero/Adept_UI_Hero_header.*`) | Adept FilmWorks brand assets | Product branding; do not redistribute separately without permission |
| Brand marks (`/brand`, `/favicon`) | Adept FilmWorks | Trademark reserved |

## Rules

- Runtime UI must load imagery from this local library only — no external image URLs.
- When replacing SVGs with photographs or AI-generated stills, record commercial-use confirmation here (source, date, license).
- Prefer WebP/JPG for photographic replacements; keep SVG plates as `onError` fallbacks via Aurora plate classes.
