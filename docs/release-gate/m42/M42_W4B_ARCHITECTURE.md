# M42 Wave 4B — MAGI Editor Architecture

| Field | Value |
|---|---|
| **Phase** | M42 Phase 4.2 Wave 4B — Adept UI MAGI Editor Foundation |
| **Branch** | phase2/m42-magi-editor-foundation |
| **Baseline** | Wave 4 GO (wave4Go: true) |

## Product identity

- **Product:** Adept UI MAGI Editor
- **Tagline:** Cut. Change. Create. All Types. All Takes.
- **Anadriya:** Adept UI face / logo identity
- **Korri:** MAGI presentation mascot only (never runtime)

## Canonical image path (Production Ready)

`	ext
CreativeContext → ImageEditIntent → Unified Resolver → pinned Runtime
→ QueueWorker → Output Gate → Provenance → Version Graph
`

## Shell layout

Media Browser + Asset Browser | Viewer / Image Canvas / MAGI Command / Actions / Recipes | Inspector / Versions / Deferred rail | Timeline stub (Draft)

Package: studio-api/app/magi/, UI: studio-web/src/components/magi/.
