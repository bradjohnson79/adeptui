"""Model Radar discovery + registry service (fixture-capable)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..fixtures import fixture_github_discoveries, fixture_hf_discoveries, require_fixture_or_allow_live
from .store import RadarStore

VALID_CLASSIFICATIONS = frozenset(
    {"official", "community", "announcement_only", "gated", "api_only"}
)


class RadarService:
    @staticmethod
    def discover(db: Session, *, source: str) -> dict[str, Any]:
        if not require_fixture_or_allow_live():
            # Production live campaigns are M2.10 — refuse unless fixture mode.
            return {
                "source": source,
                "entries": [],
                "created": 0,
                "duplicatesSuppressed": 0,
                "mode": "live_disabled",
                "message": "Live discovery disabled. Set ADEPT_M28_FIXTURE_MODE=1 for fixtures.",
            }

        if source == "huggingface":
            discoveries = fixture_hf_discoveries()
        elif source == "github":
            discoveries = fixture_github_discoveries()
        else:
            raise ValueError(f"Unsupported discovery source: {source}")

        before = {(e["source"], e["sourceKey"]) for e in RadarStore.list_entries(db)}
        created = 0
        suppressed = 0
        entries: list[dict[str, Any]] = []
        for item in discoveries:
            classification = item["classification"]
            if classification not in VALID_CLASSIFICATIONS:
                classification = "community"
            key = (item["source"], item["source_key"])
            if key in before:
                suppressed += 1
            else:
                created += 1
                before.add(key)
            entry = RadarStore.upsert_entry(
                db,
                source=item["source"],
                source_key=item["source_key"],
                display_name=item["display_name"],
                classification=classification,
                metadata=item.get("metadata") or {},
            )
            entries.append(entry)
        return {
            "source": source,
            "entries": entries,
            "created": created,
            "duplicatesSuppressed": suppressed,
            "mode": "fixture",
        }

    @staticmethod
    def registry(db: Session) -> list[dict[str, Any]]:
        return RadarStore.list_entries(db)

    @staticmethod
    def add_to_watchlist(
        db: Session, *, entry_id: str, project_id: str | None = None
    ) -> dict[str, Any]:
        entry = RadarStore.get_entry(db, entry_id)
        if not entry:
            raise LookupError("Model entry not found")
        return RadarStore.add_watchlist(db, entry_id=entry_id, project_id=project_id)
