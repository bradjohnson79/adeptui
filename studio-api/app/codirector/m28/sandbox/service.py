"""Isolated sandbox lifecycle + install plan approval (M2.7 job gated)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import ensure_m28_tables
from ..fixtures import (
    assert_path_inside_sandbox,
    fixture_execution_enabled,
    sandbox_root,
    simulate_sandbox_detect,
)
from ..radar.store import RadarStore


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sandbox_fixtures_enabled() -> bool:
    """Simulated sandbox execution is CI-only (ADEPT_M28_FIXTURE_MODE / STUDIO_E2E)."""
    return fixture_execution_enabled()


class SandboxService:
    @staticmethod
    def create(db: Session, *, name: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        ensure_m28_tables()
        sid = str(uuid.uuid4())
        port = 19000 + (abs(hash(sid)) % 1000)
        now = _now()
        root = sandbox_root(sid)
        cfg = {"root": str(root), "productionComfyUntouched": True, **(config or {})}
        db.execute(
            text(
                "INSERT INTO m28_sandbox_instances "
                "(id, name, status, config_json, port, created_at, updated_at) "
                "VALUES (:id, :name, :status, :config_json, :port, :created_at, :updated_at)"
            ),
            {
                "id": sid,
                "name": name,
                "status": "created",
                "config_json": json.dumps(cfg),
                "port": port,
                "created_at": now,
                "updated_at": now,
            },
        )
        db.commit()
        return SandboxService.get(db, sid)  # type: ignore[return-value]

    @staticmethod
    def get(db: Session, sandbox_id: str) -> Optional[dict[str, Any]]:
        ensure_m28_tables()
        row = db.execute(
            text(
                "SELECT id, name, status, config_json, port, created_at, updated_at "
                "FROM m28_sandbox_instances WHERE id = :id"
            ),
            {"id": sandbox_id},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "status": row["status"],
            "config": json.loads(row["config_json"] or "{}"),
            "port": row["port"],
            "createdAt": str(row["created_at"]),
            "updatedAt": str(row["updated_at"]),
            "productionComfyUntouched": True,
        }

    @staticmethod
    def _set_status(db: Session, sandbox_id: str, status: str) -> dict[str, Any]:
        db.execute(
            text(
                "UPDATE m28_sandbox_instances SET status = :status, updated_at = :updated_at "
                "WHERE id = :id"
            ),
            {"id": sandbox_id, "status": status, "updated_at": _now()},
        )
        db.commit()
        out = SandboxService.get(db, sandbox_id)
        if not out:
            raise LookupError("Sandbox not found")
        return out

    @staticmethod
    def start(db: Session, sandbox_id: str) -> dict[str, Any]:
        if not SandboxService.get(db, sandbox_id):
            raise LookupError("Sandbox not found")
        return SandboxService._set_status(db, sandbox_id, "running")

    @staticmethod
    def stop(db: Session, sandbox_id: str) -> dict[str, Any]:
        return SandboxService._set_status(db, sandbox_id, "stopped")

    @staticmethod
    def restart(db: Session, sandbox_id: str) -> dict[str, Any]:
        SandboxService.stop(db, sandbox_id)
        return SandboxService.start(db, sandbox_id)

    @staticmethod
    def health(db: Session, sandbox_id: str) -> dict[str, Any]:
        sb = SandboxService.get(db, sandbox_id)
        if not sb:
            raise LookupError("Sandbox not found")
        ok = sb["status"] in {"running", "validated", "created"}
        return {"sandboxId": sandbox_id, "ok": ok, "status": sb["status"]}

    @staticmethod
    def detect(db: Session, sandbox_id: str) -> dict[str, Any]:
        if not SandboxService.get(db, sandbox_id):
            raise LookupError("Sandbox not found")
        return simulate_sandbox_detect(sandbox_id)

    @staticmethod
    def create_plan(
        db: Session, *, sandbox_id: str, entry_id: str
    ) -> dict[str, Any]:
        sb = SandboxService.get(db, sandbox_id)
        if not sb:
            raise LookupError("Sandbox not found")
        entry = RadarStore.get_entry(db, entry_id)
        if not entry:
            raise LookupError("Model entry not found")
        if entry["classification"] == "announcement_only":
            raise ValueError("Announcement-only entries have no install action")

        root = sandbox_root(sandbox_id)
        target = root / "models" / entry["sourceKey"].replace("/", "__")
        assert_path_inside_sandbox(sandbox_id, target)
        plan = {
            "entryId": entry_id,
            "files": [str(target / "model.safetensors")],
            "repos": [entry["sourceKey"]],
            "commits": [(entry.get("metadata") or {}).get("commit") or "fixture-commit"],
            "diskGb": (entry.get("metadata") or {}).get("storageGb") or 1,
            "risks": ["Isolated sandbox only — production Comfy untouched"],
            "deps": (entry.get("metadata") or {}).get("deps") or [],
            "rollback": {"strategy": "delete_sandbox_root", "root": str(root)},
            "writesOutsideSandbox": False,
        }
        plan_id = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO m28_sandbox_plans (id, sandbox_id, plan_json, status, created_at) "
                "VALUES (:id, :sandbox_id, :plan_json, :status, :created_at)"
            ),
            {
                "id": plan_id,
                "sandbox_id": sandbox_id,
                "plan_json": json.dumps(plan),
                "status": "pending",
                "created_at": _now(),
            },
        )
        db.commit()
        return {"id": plan_id, "sandboxId": sandbox_id, "status": "pending", "plan": plan}

    @staticmethod
    def get_plan(db: Session, plan_id: str) -> Optional[dict[str, Any]]:
        ensure_m28_tables()
        row = db.execute(
            text(
                "SELECT id, sandbox_id, plan_json, status, created_at "
                "FROM m28_sandbox_plans WHERE id = :id"
            ),
            {"id": plan_id},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "sandboxId": row["sandbox_id"],
            "status": row["status"],
            "plan": json.loads(row["plan_json"] or "{}"),
            "createdAt": str(row["created_at"]),
        }

    @staticmethod
    def reject_plan(db: Session, plan_id: str) -> dict[str, Any]:
        plan = SandboxService.get_plan(db, plan_id)
        if not plan:
            raise LookupError("Plan not found")
        db.execute(
            text("UPDATE m28_sandbox_plans SET status = 'rejected' WHERE id = :id"),
            {"id": plan_id},
        )
        db.commit()
        plan["status"] = "rejected"
        plan["environmentChanged"] = False
        return plan

    @staticmethod
    def approve_plan(
        db: Session,
        *,
        plan_id: str,
        project_id: str,
        owner: str = "user",
    ) -> dict[str, Any]:
        """Approve plan by creating an M2.7 Production Job — does not bypass orchestration."""
        plan = SandboxService.get_plan(db, plan_id)
        if not plan:
            raise LookupError("Plan not found")
        if plan["status"] == "rejected":
            raise ValueError("Cannot approve a rejected plan")

        from ...executive.models import JobType
        from ...executive.schemas import CreateJobRequest
        from ...executive.service import ProductionExecutiveService

        ProductionExecutiveService.ensure_worker()
        job = ProductionExecutiveService.create_job(
            db,
            CreateJobRequest(
                type=JobType.SANDBOX_INSTALL,
                projectId=project_id,
                owner=owner,
                payload={
                    "planId": plan_id,
                    "sandboxId": plan["sandboxId"],
                    "approved": True,
                },
            ),
        )
        db.execute(
            text("UPDATE m28_sandbox_plans SET status = 'approved' WHERE id = :id"),
            {"id": plan_id},
        )
        db.commit()
        plan["status"] = "approved"
        plan["job"] = job.model_dump()
        return plan

    @staticmethod
    def execute_approved_install(db: Session, *, plan_id: str) -> dict[str, Any]:
        """Perform an approved sandbox install.

        No real installer is wired yet: outside an env-gated fixture run this refuses
        rather than writing a marker file and reporting `installed`.
        """
        plan = SandboxService.get_plan(db, plan_id)
        if not plan:
            raise LookupError("Plan not found")
        if plan["status"] != "approved":
            raise PermissionError("Install requires approved plan — no silent install")
        if not sandbox_fixtures_enabled():
            raise PermissionError(
                "Sandbox install is unavailable: no real sandbox installer is wired, and "
                "simulated installs require ADEPT_M28_FIXTURE_MODE / STUDIO_E2E. "
                "The plan stays approved and nothing was installed."
            )
        root = sandbox_root(plan["sandboxId"])
        model_dir = root / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        marker = model_dir / "installed.fixture"
        assert_path_inside_sandbox(plan["sandboxId"], marker)
        marker.write_text("fixture-installed\n", encoding="utf-8")
        db.execute(
            text("UPDATE m28_sandbox_plans SET status = 'executed' WHERE id = :id"),
            {"id": plan_id},
        )
        SandboxService._set_status(db, plan["sandboxId"], "installed")
        return {
            "planId": plan_id,
            "installed": True,
            "root": str(root),
            "fixtureMode": True,
            "honesty": "Simulated fixture install (CI only) — no model weights were fetched.",
        }

    @staticmethod
    def validate(db: Session, sandbox_id: str) -> dict[str, Any]:
        """Validate a sandbox. Refuses outside CI rather than reporting a fixture pass."""
        sb = SandboxService.get(db, sandbox_id)
        if not sb:
            raise LookupError("Sandbox not found")
        if not sandbox_fixtures_enabled():
            raise PermissionError(
                "Sandbox validation is unavailable: no real sandbox runtime is wired, and "
                "the fixture runtime requires ADEPT_M28_FIXTURE_MODE / STUDIO_E2E."
            )
        result = {
            "ok": True,
            "runtime": "fixture-sandbox",
            "fixtureMode": True,
            "mockVram": {"usedGb": 4, "totalGb": 24},
            "output": {"preview": "fixture-ok"},
            "warnings": ["Fixture runtime — not evidence of a working model install."],
            "errors": [],
            "productionComfyUntouched": True,
        }
        vid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO m28_sandbox_validations (id, sandbox_id, result_json, created_at) "
                "VALUES (:id, :sandbox_id, :result_json, :created_at)"
            ),
            {
                "id": vid,
                "sandbox_id": sandbox_id,
                "result_json": json.dumps(result),
                "created_at": _now(),
            },
        )
        SandboxService._set_status(db, sandbox_id, "validated")
        return {"id": vid, "sandboxId": sandbox_id, "result": result}

    @staticmethod
    def remove(db: Session, sandbox_id: str) -> dict[str, Any]:
        sb = SandboxService.get(db, sandbox_id)
        if not sb:
            raise LookupError("Sandbox not found")
        import shutil

        root = sandbox_root(sandbox_id)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        SandboxService._set_status(db, sandbox_id, "removed")
        return {
            "sandboxId": sandbox_id,
            "removed": True,
            "productionComfyUntouched": True,
        }
