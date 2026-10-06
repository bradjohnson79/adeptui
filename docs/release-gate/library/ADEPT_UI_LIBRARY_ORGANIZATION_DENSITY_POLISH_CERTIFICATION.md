# Adept UI Library Organization + Density Polish

**Governing document for this milestone.**

Layout and information-architecture polish of the existing Project / Global Library. The asset model is unchanged.

**Verdict:** `GO — ADEPT UI LIBRARY ORGANIZATION + DENSITY POLISH E2E CERTIFIED`

---

## Identity

| Field | Value |
| --- | --- |
| Branch | `feat/character-creator-final-closure` |
| HEAD SHA | `b6156455` (working tree includes this mission; not committed unless requested) |
| Named project | Korri Anadriya `beffd3d8-791d-4adf-9c4d-681ec9d4efb0` |
| Review URL | `http://127.0.0.1:5173/project/beffd3d8-791d-4adf-9c4d-681ec9d4efb0?workspace=library` |
| Studio API | `http://127.0.0.1:8758/` |

Success string: `GO — ADEPT UI LIBRARY ORGANIZATION + DENSITY POLISH E2E CERTIFIED`

Failure string: `NO-GO — ADEPT UI LIBRARY ORGANIZATION + DENSITY POLISH INCOMPLETE`

---

## Classification

**Layout / density:** WRONG before this journey (functioning asset system, loose IA).

Smoking gun: `.library-layout` was a 2-column grid with 3 children, so the asset pane collapsed to ~320px and cards stacked in two skinny columns on a wide desktop.

This journey does **not** rewrite:

- `assetModel.ts`
- Library API contracts
- Co-Director `LibraryMediaGrid` test ids
- MAGI grids
- Home project library

---

## Architecture (visual only)

```text
Assets first
  Project / Global
  search
  Type chips
  Model / References / Favorites + Selection (grouped, not one undifferentiated row)
  two-or-three pane:
    left  = Folders (compact, 200px)
    main  = asset grid (auto-fill min 160px)
    right = Asset Graph + optional Details (beside the selected card)

Then collapsible packs (collapsed when empty):
  Timeline Sequences
  Editor Sequences
  Scene Master Sheets
  Avatars
  Production Collections
```

Creator-facing type chips (client-side over existing `kind` / folder / labels):

Images · Video · Audio · Characters · Props · Scenes · Environments · Storyboards · Scripts · Presets/Templates

Model chips keep stored values (`zimage`, `flux`, `qwen`, `imagen`, `krea2`) and show Z-Image / Flux / Qwen / Imagen / Krea 2.

Video / audio without a thumbnail use a compact media placeholder (type icon + filename + model tag), not a giant empty “video” block.

Empty packs use `.library-empty-compact` rows, not full-height empty panels.

---

## Live proof

Playwright `tests/e2e/library/library-organization-density.spec.ts` — **1 passed** (4.2s) on Korri:

```text
open Project Library
→ search
→ Filter Video
→ Filter Audio
→ Filter Qwen
→ reset All / All
→ select an asset → Asset Graph (+ Details if present)
→ open a collection when one exists
→ All assets
→ Global Library
→ reload
→ layout remains ≥2 columns
```

Live Vite 1600×960 on Korri Project Library:

- Three-pane layout: Folders · dense grid · Asset Graph
- Type / Model / References grouped
- Asset grid **5 columns** on the wide pane (no two-column dead center)
- Selected card keeps a cyan border; Asset Graph populates beside the grid
- Video cards show a compact play-icon placeholder + filename + model tag
- Sequence / avatar packs stay compact when empty

---

## Tests (this run)

| Suite | Result |
| --- | --- |
| Playwright `library-organization-density.spec.ts` | **1 passed** |

Preserved test ids: `library-filters`, `library-collections`, `library-new-collection`, `library-provenance`, headings `/^Libraries$/` and `/^Folders$/`.

Added: `library-search`, `library-scope-project`, `library-scope-global`, `library-type-nav`, `library-filter-images|video|audio`, `library-filter-model-*`, `library-section-assets`, `library-asset-card`, `library-empty-compact`.

---

## Runtime

- `http://127.0.0.1:8758/api/healthz` → 200
- `http://127.0.0.1:5173/` → 200
- `GET http://127.0.0.1:8188/system_stats` → 200 (leave-alone)

**COMFY BEFORE:** PID **69108**, health 200  
**COMFY AFTER:** PID **69108**, health 200  
**COMFY RESTARTED?:** NO  
**WHY?:** Library CSS / panel polish only. No supervisor restart.

---

## E2E TRACE

| Stage | Result |
| --- | --- |
| User action | PASS — Project Library → search → Video / Audio / Qwen → select → collection → All assets → Global → reload |
| Frontend | PASS — 3-pane density; type + grouped filters; Asset Graph beside selection |
| API | N/A — no asset-model or endpoint rewrite |
| Backend | N/A |
| Persistence | PASS — existing assets / favorites / collections unchanged |
| Runtime | PASS — Vite HMR / existing API; Comfy untouched |
| Result | PASS — professional production browser, not a diagnostic page |
| Reload | PASS — layout and Library chrome remain coherent |
| Downstream | PASS — Timeline / Scene Creator / Co-Director Library access not retargeted |

---

## Limitations

- Folder tree still lists every child folder (existing hierarchy). Type chips are the clearer parent filter.
- Generation / provenance notes stay behind **Details**, not in default chrome.
- Search still updates `q` on each keystroke (pre-existing; not in this polish).
- Production Collections with zero assets still exist on Korri; the pack is compact rows, not a tall empty panel.
- Working tree is not committed unless requested.

---

## Final verdict

**GO — ADEPT UI LIBRARY ORGANIZATION + DENSITY POLISH E2E CERTIFIED**
