# M4.9 Storyboard Studio — UX Specification

## Route

`?workspace=script` (label: Storyboard Studio) mounts `StoryboardStudio`.

## Page model

- Panels per page: **6 | 9 | 12** (default **9**)
- Page navigation + drag reorder
- Script link badges: Linked / Script Updated / Override / Conflict / Unlinked

## Actions

- Open in Image Generator (seeds prompt + continuity session)
- Prepare for Timeline → reviewable proposal only (no silent clips)
- Image Generator → Add to Storyboard fills next free slot with Undo

## Export

PDF / contact sheets / Adept JSON — follow-on export pass (API + UI).
