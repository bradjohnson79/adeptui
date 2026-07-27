"""Route B: imported 3D environment normalize -> register -> approve."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .convert_worker import convert_to_glb
from .db import ensure_m213_tables
from .import_security import validate_import_file
from .store import M213Store


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_and_register(
    db: Session,
    *,
    project_id: str,
    source_path: str,
    title: str = "Imported Environment",
    scene_id: str | None = None,
    fixture: bool = False,
) -> dict[str, Any]:
    ensure_m213_tables()
    validation = validate_import_file(source_path)
    if not validation.ok and not fixture:
        return {"ok": False, "validation": validation.to_dict(), "route": "imported_3d"}
    convert = None
    asset_kind = "3d.environment"
    glb_path = source_path
    if fixture:
        validation.fixture = True
        validation.ok = True
        convert = {
            "ok": True,
            "mode": "fixture",
            "outputPath": source_path,
            "message": "Fixture import path (CI). Not a real mesh conversion.",
            "blenderDetected": False,
            "authoringSupported": False,
            "fixture": True,
        }
    else:
        dest = Path(source_path).parent / "_m213_normalized"
        convert_res = convert_to_glb(source_path, dest)
        convert = convert_res.to_dict()
        if not convert_res.ok and Path(source_path).suffix.lower() != ".glb":
            return {
                "ok": False,
                "validation": validation.to_dict(),
                "convert": convert,
                "route": "imported_3d",
            }
        if convert_res.output_path:
            glb_path = convert_res.output_path
    env_id = str(uuid.uuid4())
    summary = {
        "route": "imported_3d",
        "sourcePath": source_path,
        "normalizedPath": glb_path,
        "validation": validation.to_dict(),
        "convert": convert,
        "inspect": {
            "title": title,
            "polyEstimate": None if fixture else "unknown",
            "notes": "Co-Director inspect summary (scaffold).",
            "fixture": fixture,
        },
        "honesty": {
            "fixture": fixture,
            "realMeshConversion": bool(convert and convert.get("mode") == "blender"),
        },
    }
    db.execute(
        text(
            "INSERT INTO m213_virtual_environments "
            "(id, project_id, scene_id, route, status, title, asset_id, summary_json, approved, approved_at, created_at, updated_at) "
            "VALUES (:id, :project_id, :scene_id, :route, :status, :title, :asset_id, :summary_json, 0, NULL, :created_at, :updated_at)"
        ),
        {
            "id": env_id,
            "project_id": project_id,
            "scene_id": scene_id,
            "route": "imported_3d",
            "status": "registered",
            "title": title,
            "asset_id": None,
            "summary_json": json.dumps(summary),
            "created_at": _now(),
            "updated_at": _now(),
        },
    )
    db.commit()
    M213Store.log_capability(
        db,
        capability_id="ve.environment.imported",
        action="register",
        project_id=project_id,
        payload={"environmentId": env_id, "fixture": fixture},
    )
    M213Store.save_version(
        db,
        project_id=project_id,
        subject_kind="environment",
        subject_id=env_id,
        version=1,
        snapshot=summary,
    )
    return {
        "ok": True,
        "environmentId": env_id,
        "route": "imported_3d",
        "status": "registered",
        "approved": False,
        "approvalGate": "environment",
        "assetKind": asset_kind,
        "summary": summary,
        "fixture": fixture,
    }


def approve_environment(
    db: Session, *, environment_id: str, actor: str = "user", note: str = ""
) -> dict[str, Any]:
    ensure_m213_tables()
    row = db.execute(
        text("SELECT id, project_id, approved FROM m213_virtual_environments WHERE id = :id"),
        {"id": environment_id},
    ).mappings().first()
    if not row:
        raise LookupError("environment not found")
    if row["approved"]:
        return {"ok": True, "environmentId": environment_id, "approved": True, "alreadyApproved": True}
    db.execute(
        text(
            "UPDATE m213_virtual_environments SET approved = 1, approved_at = :ts, status = 'approved', updated_at = :ts "
            "WHERE id = :id"
        ),
        {"id": environment_id, "ts": _now()},
    )
    db.commit()
    approval = M213Store.record_approval(
        db,
        project_id=row["project_id"],
        gate="environment",
        subject_id=environment_id,
        approved=True,
        actor=actor,
        note=note,
    )
    return {"ok": True, "environmentId": environment_id, "approved": True, "approval": approval}
