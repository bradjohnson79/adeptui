# Knowledge Cards

## Model (`app/codirector/story_intelligence/knowledge_card.py`)

### Types
- STORY, CHARACTER, VISION, PROJECT_STYLE

### Status Lifecycle
```
DRAFT → READY_FOR_REVIEW → EDITING → APPROVED_FOR_ADD → ADDED
                                   ↘ DISMISSED
                                   ↘ FAILED
```

### Key Functions
- `create_card` — creates DRAFT card, stores in ephemeral session dict
- `generate_card_from_conversation` — builds structured card from conversation context
- `add_card_to_project` — routes approved payload to authoritative system
- `dismiss_card` — zero authoritative mutation
- `update_card` — edit card fields before Add

### Add Paths
- CHARACTER → Character Identity (create_profile / update_profile)
- STORY → compiledWiki storySummary
- VISION → snapshot.vision
- PROJECT_STYLE → snapshot.style

### Add = Commit Pinned Payload
Card payload is created at generation time. Add commits the exact same payload.
No hidden recomputation at Add time. If project state changed → surface conflict.

### API (`app/codirector/routers/knowledge.py`)
- `POST /api/knowledge-cards/{card_id}/add`
- `POST /api/knowledge-cards/{card_id}/dismiss`
- `POST /api/knowledge-cards/{card_id}/edit`
- `GET /api/knowledge-cards/project/{project_id}`

## Wiki Auto-Extraction Disabled
- `wiki_intelligence/orchestrator.py:_apply_decisions` — returns 0, no auto-persist
- `conversation/orchestrate.py` — wiki_candidates=[], shouldWriteWiki=False
- `wiki_intelligence/classification.py` — entity detection returns "note" (understanding only)

## Four Opening Cards (empty projects)
- Talk about the Story
- Talk about a Character
- Talk about your Vision
- Talk about the Project Style
