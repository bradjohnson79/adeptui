"""Production State invalidation — read-through freshness markers.

Law 4: invalidation marks cached projection state as stale; the actual
recomputation happens on next read (read-through). No writable projection store.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .contracts import ProjectionDomain
from ..conversation.project_cache import invalidate_cache_sections

logger = logging.getLogger(__name__)


def invalidate_production_state(
    db: Session,
    project_id: str,
    *,
    affected_domains: set[ProjectionDomain] | None = None,
) -> None:
    """Mark the production state projection as stale for *project_id*.

    Delegates to ``project_cache.invalidate_cache_sections`` with the
    ``"production_state"`` section key.  If *affected_domains* is provided the
    specific domains are logged for observability; the actual recomputation
    occurs on next read (read-through projection).
    """
    if affected_domains:
        domain_names = sorted(d.value for d in affected_domains)
        logger.info(
            "Invalidating production state for project %s — affected domains: %s",
            project_id,
            ", ".join(domain_names),
        )
    else:
        logger.debug("Invalidating production state for project %s", project_id)

    invalidate_cache_sections(db, project_id, ["production_state"])


def invalidate_for_all_mutations(
    affected_domains_by_channel: dict[str, set[ProjectionDomain]],
) -> None:
    """Registration-only placeholder.

    Phase 2 does NOT wire individual mutation hooks (those are Phase 6 Workflow
    Engine territory).  Each mutation that wants to invalidates production state
    calls ``invalidate_production_state(db, project_id)`` directly.

    This function exists as a contract placeholder so the design is accepted
    and the signature is reserved for later orchestration.
    """
    logger.debug(
        "invalidate_for_all_mutations called with %d channels (no-op in Phase 2)",
        len(affected_domains_by_channel),
    )


# ---------------------------------------------------------------------------
# Static mutation → domain mapping for observability / documentation.
# Populated from the first 6 rows of §3 in PRODUCTION_STATE_SOURCE_AUDIT.md.
# See the full table at docs/release-gate/codirector-2/CODIRECTOR2_PRODUCTION_STATE_SOURCE_AUDIT.md
# ---------------------------------------------------------------------------
BULK_MUTATION_POINTS: dict[str, list[str]] = {
    "routers/api.py:850 update_project (name/fps/format/width/height)": [
        "PROJECT",
    ],
    "project_decisions.py:81-84 apply_record_production_decision (rename + record)": [
        "PROJECT",
        "DECISIONS",
    ],
    "scene_service.py:53 create_scene / :99 update_scene_fields (summary/duration/fps/timeline)": [
        "SCENES",
        "TIMELINE",
    ],
    "routers/api.py:1056 DELETE scene (row removal)": [
        "SCENES",
        "TIMELINE",
    ],
    "character_identity/service.py:254 update_profile (~:290-305 rename)": [
        "CHARACTERS",
    ],
    "character_identity/service.py:438 approve_version (version approval)": [
        "CHARACTERS",
    ],
}
