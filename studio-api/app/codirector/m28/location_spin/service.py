"""Location Spin hybrid chain metadata + coverage pack (fixture-capable)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import ensure_m28_tables
from ..fixtures import fixture_mode_enabled


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


HYBRID_CHAIN = [
    "master",
    "depth",
    "seg",
    "proxy",
    "stage",
    "guide",
    "refine",
    "validate",
]


class LocationSpinService:
    @staticmethod
    def plan(
        db: Session, *, project_id: str, location_name: str = "Fixture Location"
    ) -> dict[str, Any]:
        ensure_m28_tables()
        lid = str(uuid.uuid4())
        plan = {
            "locationName": location_name,
            "chain": HYBRID_CHAIN,
            "strategy": "hybrid",
            "fixtureMode": fixture_mode_enabled(),
            "notes": "master->depth->seg->proxy->stage->guide->refine->validate",
        }
        db.execute(
            text(
                "INSERT INTO m28_location_spins "
                "(id, project_id, plan_json, coverage_json, created_at) "
                "VALUES (:id, :project_id, :plan_json, :coverage_json, :created_at)"
            ),
            {
                "id": lid,
                "project_id": project_id,
                "plan_json": json.dumps(plan),
                "coverage_json": json.dumps({}),
                "created_at": _now(),
            },
        )
        db.commit()
        return {"id": lid, "projectId": project_id, "plan": plan, "coverage": None}

    @staticmethod
    def get(db: Session, spin_id: str) -> Optional[dict[str, Any]]:
        ensure_m28_tables()
        row = db.execute(
            text(
                "SELECT id, project_id, plan_json, coverage_json, created_at "
                "FROM m28_location_spins WHERE id = :id"
            ),
            {"id": spin_id},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "plan": json.loads(row["plan_json"] or "{}"),
            "coverage": json.loads(row["coverage_json"] or "{}") or None,
            "createdAt": str(row["created_at"]),
        }

    @staticmethod
    def spin_camera(
        db: Session, *, spin_id: str, angles: list[float] | None = None
    ) -> dict[str, Any]:
        item = LocationSpinService.get(db, spin_id)
        if not item:
            raise LookupError("Location spin not found")
        angles = angles or [0.0, 45.0, 90.0, 135.0, 180.0]
        coverage = {
            "packId": str(uuid.uuid4()),
            "angles": angles,
            "frames": [
                {"angle": a, "assetId": f"fixture-spin-{int(a)}", "fixture": True}
                for a in angles
            ],
            "readyForStoryboard": True,
            "fixtureMode": fixture_mode_enabled(),
        }
        db.execute(
            text("UPDATE m28_location_spins SET coverage_json = :c WHERE id = :id"),
            {"id": spin_id, "c": json.dumps(coverage)},
        )
        db.commit()
        item["coverage"] = coverage
        return item
