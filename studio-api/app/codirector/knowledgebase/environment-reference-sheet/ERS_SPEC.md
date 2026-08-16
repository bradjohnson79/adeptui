# Environment Reference Sheet (ERS) — Product Spec

This folder is the Co-Director knowledgebase for Environment Reference Sheets.
It is a **unified production-design document**, not a four-image variation collage
and not a Character Sheet.

## Canonical files

| File | Role |
| --- | --- |
| `ERS_SPEC.md` | This contract. Always loaded. |
| `ERS_REFERENCE_01.png` | GPT Image 2 exemplar — Venture Main Observation Corridor. Layout/density only. |
| `ERS_REFERENCE_02.png` | GPT Image 2 exemplar — Mother Sphere, Korri's Domocile. Layout/density only. |

Exemplars teach **structure and information density**. Never copy their content
(Venture corridor, Mother Sphere, Korri, Aiya, invented IDs, dates, or dimensions)
into a new environment.

## What NOT to copy (binding)

The exemplar PNGs in this knowledgebase show a DIFFERENT environment (a
spaceship observation corridor and a fantasy domicile). When exemplar pixels
are attached for layout conditioning:

- Do NOT copy the exemplar's architecture, windows, doors, or floor plan.
- Do NOT copy the exemplar's props, furniture, vehicles, or set dressing.
- Do NOT copy the exemplar's color palette, materials, or lighting design.
- Do NOT copy the exemplar's text, labels, logos, or annotations.
- Do NOT copy the exemplar's characters or creatures.
- Copy ONLY the sheet structure: which sections exist, roughly how much of the
  canvas each section occupies, and the information density of each section.

The Scene Intent JSON, the original environment reference image, and the
Atlas Shot define the CONTENT. The exemplars define the SHAPE of the page.

## What an ERS is

One image that a production team can use as the canonical visual + spatial
guide for a single environment. Same place throughout. Every panel is a
different *kind of information* about that place, not a different mood or
camera variation of a beauty shot.

## Required sections

The compiled prompt must ask the model to emit these sections in one sheet:

1. **Hero Environment** — canonical look of the place. Primary visual reference.
2. **Spatial / Top-Down** — floor plan. Only include scale, compass, IDs, or
   dimensions if Spatial Map / project data actually has them. Do not invent.
3. **Structural / 3D** — greybox / mesh / untextured geometry if the model can
   do it. Skip rather than fake a second hero render.
4. **Directional / Orthographic views** — North, East, South, West of the
   *same* environment. Not four cinematic POVs. Not Front / Side / Back / Close-Up.
5. **Materials** — close-up tiles for floors, walls, counters, furniture,
   equipment that actually exist in this environment.
6. **Lighting** — primary / secondary / accent sources that belong to this place.
7. **Environment DNA** — era, visual language, condition, emotional register
   (intimate / warm / lived-in, industrial / functional, etc.) taken from the
   scene, not invented lore.
8. **Continuity Rules** — Always / Never for this environment. Concrete and
   checkable (counter stays here, windows on this wall, do not turn sleek, etc.).

Optional only when the scene actually has them:

- Hero prop callout (one object that belongs to the set).
- Camera blocking overlaid on the spatial map (C1… only if cameras exist on the map).
- Environment evolution / metadata — only if project data supplies it.

## What an ERS is not

- A Character Sheet. Never Front / Side / Back / Close-Up of a person.
- A Prop Sheet. Never four views of an object as the whole document.
- Four similar beauty / POV variations of the same room.
- A single cinematic still with a title bar.
- A collage of unrelated rooms.

A result that is any of the above is `ERS_LAYOUT_NONCOMPLIANT`.

## Runtime

- Purpose: `environment_reference_sheet`.
- Default generator: **Qwen Image** (local Comfy). One prompt, one image.
- Optional generator: **GPT Image 2** (paid API). Fires only when the user
  explicitly selects it and presses Generate.
- No silent model substitution. No silent cloud fallback if Qwen fails.
- Reference images (these exemplars) attach only if the chosen model path
  supports image refs **and** attaching them is useful. They are layout
  conditioning, never content to reproduce.
- Do not invent dimensions, dates, environment IDs, or compass bearings
  unless Spatial Map / project data already has them.

## Schnick Coffee (first live target)

A Schnick Coffee ERS must look like: hero café, top-down layout, N/E/S/W of
the café, materials (floors / counters / tables / walls / equipment), lighting,
DNA (intimate / warm / lived-in), continuity (counter, tables, lights, entrances).
Not four POV glass shots. Not the Venture corridor. Not Korri's room.
