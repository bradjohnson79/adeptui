"""Compatibility evaluation against an environment profile."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import ensure_m28_tables
from ..fixtures import default_env_profile
from ..radar.store import RadarStore


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CompatService:
    @staticmethod
    def evaluate(
        db: Session,
        *,
        entry_id: str,
        env_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ensure_m28_tables()
        entry = RadarStore.get_entry(db, entry_id)
        if not entry:
            raise LookupError("Model entry not found")

        env = {**default_env_profile(), **(env_profile or {})}
        meta = entry.get("metadata") or {}
        reasons: list[str] = []
        ready = True

        need_vram = int(meta.get("vramGb") or 0)
        if need_vram > int(env.get("vramGb") or 0):
            ready = False
            reasons.append(f"Insufficient VRAM: need {need_vram}GB, have {env.get('vramGb')}GB")

        need_storage = int(meta.get("storageGb") or 0)
        if need_storage > int(env.get("storageGb") or 0):
            ready = False
            reasons.append(
                f"Insufficient storage: need {need_storage}GB, have {env.get('storageGb')}GB"
            )

        os_list = meta.get("os") or []
        if os_list and str(env.get("os") or "").lower() not in [str(x).lower() for x in os_list]:
            ready = False
            reasons.append(f"OS unsupported: host={env.get('os')} supported={os_list}")

        deps = meta.get("deps") or []
        have = {str(d).lower() for d in (env.get("deps") or [])}
        missing = [d for d in deps if str(d).lower() not in have]
        if missing:
            ready = False
            reasons.append(f"Missing dependencies: {', '.join(missing)}")

        license_name = str(meta.get("license") or "unknown")
        allowed = {str(x).lower() for x in (env.get("allowedLicenses") or [])}
        if license_name.lower() not in allowed:
            ready = False
            reasons.append(f"License not allowed: {license_name}")

        if entry["classification"] in {"announcement_only", "api_only", "gated"}:
            ready = False
            reasons.append(
                f"Classification '{entry['classification']}' is not install-ready"
            )

        verdict = "ready" if ready else "unsupported"
        if not ready and not reasons:
            reasons.append("Unsupported")

        eval_id = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO m28_compat_evals "
                "(id, entry_id, verdict, reasons_json, env_json, created_at) "
                "VALUES (:id, :entry_id, :verdict, :reasons_json, :env_json, :created_at)"
            ),
            {
                "id": eval_id,
                "entry_id": entry_id,
                "verdict": verdict,
                "reasons_json": json.dumps(reasons),
                "env_json": json.dumps(env),
                "created_at": _now(),
            },
        )
        db.commit()
        return {
            "id": eval_id,
            "entryId": entry_id,
            "verdict": verdict,
            "ready": ready,
            "reasons": reasons,
            "env": env,
            "vram": {"required": need_vram, "available": env.get("vramGb")},
            "storage": {"required": need_storage, "available": env.get("storageGb")},
            "os": env.get("os"),
            "deps": {"required": deps, "missing": missing},
            "license": license_name,
        }
