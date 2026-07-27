"""Multi-stage Production Recipes via durable M2.7 jobs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import ensure_m28_tables
from ..fixtures import fixture_execution_enabled, mock_generation_result


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RecipeService:
    @staticmethod
    def create(
        db: Session,
        *,
        project_id: str,
        name: str,
        stages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        ensure_m28_tables()
        rid = str(uuid.uuid4())
        stage_defs = stages or [
            {"name": "base", "kind": "generate"},
            {"name": "lighting", "kind": "generate"},
            {"name": "grade", "kind": "generate"},
        ]
        db.execute(
            text(
                "INSERT INTO m28_recipes (id, project_id, name, status, manifest_json, created_at) "
                "VALUES (:id, :project_id, :name, :status, :manifest_json, :created_at)"
            ),
            {
                "id": rid,
                "project_id": project_id,
                "name": name,
                "status": "pending",
                "manifest_json": json.dumps({"stages": stage_defs}),
                "created_at": _now(),
            },
        )
        for idx, stage in enumerate(stage_defs):
            db.execute(
                text(
                    "INSERT INTO m28_recipe_stages "
                    "(id, recipe_id, stage_index, job_id, status, payload_json) "
                    "VALUES (:id, :recipe_id, :stage_index, NULL, :status, :payload_json)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "recipe_id": rid,
                    "stage_index": idx,
                    "status": "pending",
                    "payload_json": json.dumps(stage),
                },
            )
        db.commit()
        return RecipeService.get(db, rid)  # type: ignore[return-value]

    @staticmethod
    def get(db: Session, recipe_id: str) -> Optional[dict[str, Any]]:
        ensure_m28_tables()
        row = db.execute(
            text(
                "SELECT id, project_id, name, status, manifest_json, created_at "
                "FROM m28_recipes WHERE id = :id"
            ),
            {"id": recipe_id},
        ).mappings().first()
        if not row:
            return None
        stages = db.execute(
            text(
                "SELECT id, stage_index, job_id, status, payload_json "
                "FROM m28_recipe_stages WHERE recipe_id = :rid ORDER BY stage_index"
            ),
            {"rid": recipe_id},
        ).mappings().all()
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "name": row["name"],
            "status": row["status"],
            "manifest": json.loads(row["manifest_json"] or "{}"),
            "createdAt": str(row["created_at"]),
            "stages": [
                {
                    "id": s["id"],
                    "stageIndex": s["stage_index"],
                    "jobId": s["job_id"],
                    "status": s["status"],
                    "payload": json.loads(s["payload_json"] or "{}"),
                }
                for s in stages
            ],
        }

    @staticmethod
    def run(
        db: Session,
        *,
        recipe_id: str,
        simulate_failure_at: int | None = None,
        owner: str = "user",
    ) -> dict[str, Any]:
        recipe = RecipeService.get(db, recipe_id)
        if not recipe:
            raise LookupError("Recipe not found")

        from ...executive.models import JobType
        from ...executive.schemas import CreateJobRequest
        from ...executive.service import ProductionExecutiveService

        ProductionExecutiveService.ensure_worker()
        prev_job_id: str | None = None
        for stage in recipe["stages"]:
            if stage["status"] == "completed":
                prev_job_id = stage["jobId"]
                continue  # resume without duplicating successful stages

            force_fail = simulate_failure_at is not None and stage["stageIndex"] == simulate_failure_at
            job = ProductionExecutiveService.create_job(
                db,
                CreateJobRequest(
                    type=JobType.RECIPE_STAGE,
                    projectId=recipe["projectId"],
                    owner=owner,
                    dependsOnJobIds=[prev_job_id] if prev_job_id else [],
                    payload={
                        "recipeId": recipe_id,
                        "stageId": stage["id"],
                        "stageIndex": stage["stageIndex"],
                        "simulateProviderFailure": force_fail,
                        "stage": stage["payload"],
                    },
                ),
            )
            db.execute(
                text(
                    "UPDATE m28_recipe_stages SET job_id = :job_id, status = :status "
                    "WHERE id = :id"
                ),
                {
                    "id": stage["id"],
                    "job_id": job.id,
                    "status": "queued",
                },
            )
            prev_job_id = job.id
        db.execute(
            text("UPDATE m28_recipes SET status = 'running' WHERE id = :id"),
            {"id": recipe_id},
        )
        db.commit()
        return RecipeService.get(db, recipe_id)  # type: ignore[return-value]

    @staticmethod
    def complete_stage(
        db: Session,
        *,
        recipe_id: str,
        stage_id: str,
        failed: bool = False,
    ) -> dict[str, Any]:
        """Record the outcome of a recipe stage.

        The only stage result available is `mock_generation_result`, so completing a stage
        outside an env-gated fixture run would mark a recipe `completed` against an asset
        that was never generated. Refuse instead; the executive maps this to Blocked.
        """
        if not fixture_execution_enabled():
            raise PermissionError(
                "Recipe stage completion is unavailable: recipe stages have no real "
                "generation backend wired, and simulated stage results require "
                "ADEPT_M28_FIXTURE_MODE / STUDIO_E2E."
            )
        result = mock_generation_result(stage=stage_id)
        status = "failed" if failed else "completed"
        db.execute(
            text(
                "UPDATE m28_recipe_stages SET status = :status, "
                "payload_json = json_patch(payload_json, :patch) WHERE id = :id"
            ),
            {"id": stage_id, "status": status, "patch": json.dumps({"result": result})},
        )
        # SQLite may not have json_patch — fallback rewrite.
        try:
            db.commit()
        except Exception:
            db.rollback()
            row = db.execute(
                text("SELECT payload_json FROM m28_recipe_stages WHERE id = :id"),
                {"id": stage_id},
            ).scalar()
            payload = json.loads(row or "{}")
            payload["result"] = result
            db.execute(
                text(
                    "UPDATE m28_recipe_stages SET status = :status, payload_json = :payload "
                    "WHERE id = :id"
                ),
                {
                    "id": stage_id,
                    "status": status,
                    "payload": json.dumps(payload),
                },
            )
            db.commit()

        recipe = RecipeService.get(db, recipe_id)
        assert recipe
        if any(s["status"] == "failed" for s in recipe["stages"]):
            db.execute(
                text("UPDATE m28_recipes SET status = 'failed' WHERE id = :id"),
                {"id": recipe_id},
            )
        elif all(s["status"] == "completed" for s in recipe["stages"]):
            manifest = {
                "recipeId": recipe_id,
                "stages": [
                    {
                        "stageIndex": s["stageIndex"],
                        "status": s["status"],
                        "result": (s.get("payload") or {}).get("result"),
                    }
                    for s in recipe["stages"]
                ],
            }
            db.execute(
                text(
                    "UPDATE m28_recipes SET status = 'completed', manifest_json = :m "
                    "WHERE id = :id"
                ),
                {"id": recipe_id, "m": json.dumps(manifest)},
            )
        db.commit()
        return RecipeService.get(db, recipe_id)  # type: ignore[return-value]

    @staticmethod
    def retry_failed(db: Session, *, recipe_id: str, owner: str = "user") -> dict[str, Any]:
        recipe = RecipeService.get(db, recipe_id)
        if not recipe:
            raise LookupError("Recipe not found")
        for stage in recipe["stages"]:
            if stage["status"] == "failed":
                db.execute(
                    text(
                        "UPDATE m28_recipe_stages SET status = 'pending', job_id = NULL "
                        "WHERE id = :id"
                    ),
                    {"id": stage["id"]},
                )
        db.execute(
            text("UPDATE m28_recipes SET status = 'pending' WHERE id = :id"),
            {"id": recipe_id},
        )
        db.commit()
        return RecipeService.run(db, recipe_id=recipe_id, owner=owner)
