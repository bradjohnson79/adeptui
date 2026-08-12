"""Durable ProductionIntent persistence (JSON under data/production_intents)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

from .schemas import ProductionIntent, SpecialistHandoff

_REPO_ROOT = Path(__file__).resolve().parents[4]
_STORE_ROOT = _REPO_ROOT / "data" / "production_intents"
_lock = threading.Lock()
_instance: Optional["IntentStore"] = None


class IntentStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _STORE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        d = self.root / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, intent: ProductionIntent) -> ProductionIntent:
        path = self._project_dir(intent.projectId) / f"{intent.intentId}.json"
        with _lock:
            path.write_text(intent.model_dump_json(indent=2), encoding="utf-8")
        return intent

    def get(self, project_id: str, intent_id: str) -> Optional[ProductionIntent]:
        path = self._project_dir(project_id) / f"{intent_id}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProductionIntent.model_validate(data)

    def list(self, project_id: str) -> list[ProductionIntent]:
        d = self._project_dir(project_id)
        out: list[ProductionIntent] = []
        for p in sorted(d.glob("*.json")):
            if p.name.startswith("handoff_"):
                continue
            try:
                out.append(ProductionIntent.model_validate(json.loads(p.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return out

    def update_state(
        self,
        project_id: str,
        intent_id: str,
        *,
        execution_state: Optional[str] = None,
        approval_policy: Optional[str] = None,
        job_id: Optional[str] = None,
        workflow_key: Optional[str] = None,
        workflow_id: Optional[str] = None,
        workflow_version: Optional[str] = None,
        certification_record_id: Optional[str] = None,
        metadata_patch: Optional[dict[str, Any]] = None,
    ) -> Optional[ProductionIntent]:
        intent = self.get(project_id, intent_id)
        if intent is None:
            return None
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        data = intent.model_dump()
        if execution_state:
            data["executionState"] = execution_state
        if approval_policy:
            data["approvalPolicy"] = approval_policy
        if job_id:
            data["jobId"] = job_id
        if workflow_key:
            data["workflowKey"] = workflow_key
        if workflow_id:
            data["workflowId"] = workflow_id
        if workflow_version:
            data["workflowVersion"] = workflow_version
        if certification_record_id:
            data["certificationRecordId"] = certification_record_id
        if metadata_patch:
            meta = dict(data.get("metadata") or {})
            meta.update(metadata_patch)
            data["metadata"] = meta
        data["updatedAt"] = now
        updated = ProductionIntent.model_validate(data)
        return self.save(updated)

    def save_handoff(self, handoff: SpecialistHandoff) -> SpecialistHandoff:
        path = self._project_dir(handoff.projectId) / f"handoff_{handoff.handoffId}.json"
        with _lock:
            path.write_text(handoff.model_dump_json(indent=2), encoding="utf-8")
        return handoff

    def get_handoff(self, project_id: str, handoff_id: str) -> Optional[SpecialistHandoff]:
        path = self._project_dir(project_id) / f"handoff_{handoff_id}.json"
        if not path.is_file():
            return None
        return SpecialistHandoff.model_validate(json.loads(path.read_text(encoding="utf-8")))


def get_intent_store() -> IntentStore:
    global _instance
    if _instance is None:
        _instance = IntentStore()
    return _instance
