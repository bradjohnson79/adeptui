# Prop Placement

Props follow the same canonical document model as characters and are summarized for generators as readable staging notes.

## Code paths

- Prop persistence and limits: `studio-api/app/spatial_map/service.py`, `studio-api/app/spatial_map/limits.py`
- Prompt-ready summaries: `studio-api/app/spatial_map/reference_bundle.py`

## Current behavior

- Certified flows allow up to four props.
- Prompt conditioning uses label plus location summary, and includes category/state when available.
- Storyboard metadata can preserve the selected spatial map id/version alongside the generated frame.
