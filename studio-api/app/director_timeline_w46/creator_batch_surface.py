"""Creator Batch UX surface — Systems P5 demotion + ORDER 8B Owner law.

HARD LOCK: Batch windows remain internal runtime / execution topology.
Creator UX must not treat Batch CRUD / patch / generate / approve / retake as
the primary product contract. SceneTake + Master + whole-scene generate are
the creator-facing path.

HTTP routes under ``/director-timeline/.../batches...`` remain for runtime /
migration / Gen tooling but are marked ``deprecated=True`` in OpenAPI and
annotated INTERNAL_RUNTIME_ONLY.

OWNER LAW (aligns with studio-web ``timelineBatchesCreatorUi.ts``):
  TIMELINE_BATCHES_CREATOR_UI = false

  No API default, migrate path, generate fallback, or rematerialize default may
  reintroduce creator Batch+ / Batch-first UX (minting "Batch 1", selecting
  batches[0] as a silent creator default, or enabling add/duplicate/delete batch)
  without an explicit Owner CLEAR that flips this contract.

  Empty Timeline scenes stay batchBlocks=[] until CD rematerialize / SceneTake
  materializes Execution Windows (labels: Window N, not Batch N).

FE coordination: Gen/FE should remove creator Batch track from normal UX and
call whole-scene / SceneTake contracts instead. Do not dual-write.
"""

from __future__ import annotations

from typing import Any

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

# Mirror FE Owner flag name/meaning (timelineBatchesCreatorUi.ts).
TIMELINE_BATCHES_CREATOR_UI = False

# Owner safeguard: reintroducing creator Batch-first / Batch+ UX is forbidden
# until Owner CLEAR. Keep True while TIMELINE_BATCHES_CREATOR_UI is False.
OWNER_BATCH_UX_REINTRODUCE_FORBIDDEN = True

CREATOR_BATCH_MUTATION_DISABLED = "CREATOR_BATCH_MUTATION_DISABLED"

_CREATOR_BATCH_MSG = (
    "Execution Windows are Co-Director plan / capability driven. "
    "Creator add/duplicate/delete/resize of batchBlocks is disabled; "
    "use rematerialize_execution_windows from a CD plan (and a new SceneTake "
    "when topology changes). "
    "Owner law: TIMELINE_BATCHES_CREATOR_UI=false — Batch+ / Batch-first UX "
    "must not be reintroduced without Owner CLEAR."
)

EXECUTION_WINDOW_LABEL_PREFIX = "Window"


def owner_batch_ux_reintroduce_forbidden() -> bool:
    """True when Owner forbids creator Batch+ / Batch-first mint/defaults."""
    return bool(OWNER_BATCH_UX_REINTRODUCE_FORBIDDEN) and not bool(
        TIMELINE_BATCHES_CREATOR_UI
    )


def creator_batch_mutation_blocked(reason: str = "") -> dict[str, Any]:
    """Constant error for creator batch CRUD / resize paths."""
    msg = _CREATOR_BATCH_MSG
    if reason:
        msg = f"{msg} ({reason})"
    return {
        "ok": False,
        "error": CREATOR_BATCH_MUTATION_DISABLED,
        "message": msg,
        "mock": False,
        "ownerLaw": "TIMELINE_BATCHES_CREATOR_UI=false",
    }


def empty_migrate_batch_blocks() -> list:
    """Owner-law empty migrate result: always [] while Batch UX is locked."""
    _ = owner_batch_ux_reintroduce_forbidden()
    return []


def forbid_creator_batch_first_mint(context: str = "") -> None:
    """Raise when a path is about to mint/select Batch-first creator UX."""
    if not owner_batch_ux_reintroduce_forbidden():
        return
    detail = context.strip() or "creator Batch-first mint"
    raise RuntimeError(
        f"OWNER_BATCH_UX_REINTRODUCE_FORBIDDEN: {detail}. "
        "TIMELINE_BATCHES_CREATOR_UI=false — leave batchBlocks=[] until CD "
        "rematerialize / SceneTake; do not mint Batch 1."
    )


def default_execution_window_label(index: int) -> str:
    """Window {i+1} labels — never Batch {i+1} while Owner lock holds."""
    return f"{EXECUTION_WINDOW_LABEL_PREFIX} {int(index) + 1}"


def is_legacy_batch_label(label: str | None) -> bool:
    if not label:
        return False
    return str(label).strip().startswith("Batch ")
