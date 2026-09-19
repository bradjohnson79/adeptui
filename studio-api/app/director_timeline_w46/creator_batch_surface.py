"""Creator-facing Batch surface demotion (Systems P5 — contracts first).

HARD LOCK: Batch windows remain internal runtime / execution topology.
Creator UX must not treat Batch CRUD / patch / generate / approve / retake as
the primary product contract. SceneTake + Master + whole-scene generate are
the creator-facing path.

HTTP routes under ``/director-timeline/.../batches...`` remain for runtime /
migration / Gen tooling but are marked ``deprecated=True`` in OpenAPI and
annotated INTERNAL_RUNTIME_ONLY.

FE coordination: Gen/FE should remove creator Batch track from normal UX and
call whole-scene / SceneTake contracts instead. Do not dual-write.
"""

from __future__ import annotations

# OpenAPI / router summary suffix for demoted endpoints.
INTERNAL_RUNTIME_ONLY = (
    "[INTERNAL RUNTIME ONLY — not creator UX. Batch is window topology; "
    "creator path is SceneTake / whole-scene generate. Systems P5 demotion.]"
)

# Route operation-ids (path templates) demoted from creator UX contracts.
CREATOR_DEMOTED_BATCH_OPS: frozenset[str] = frozenset(
    {
        "POST /batches",
        "POST /batches/{batch_id}/duplicate",
        "DELETE /batches/{batch_id}",
        "PATCH /batches/{batch_id}",
        "POST /batches/{batch_id}/generate",
        "POST /batches/{batch_id}/approve",
        "POST /batches/{batch_id}/reject",
        "POST /batches/{batch_id}/retake",
        "POST /batches/{batch_id}/retake-range",
        "POST /batches/{batch_id}/activate-take",
        "POST /batches/{batch_id}/repair-ranges",
        "POST /batches/{batch_id}/complete",
    }
)
