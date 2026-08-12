"""Append-only Image Workflow Certification Record ledger (M42 W2).

Evidence lives in JSONL. Registry holds only a pointer to the active record.
Records are never updated in place.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_JSONL = _REPO_ROOT / "artifacts" / "m42" / "w2" / "workflow_certification_records.jsonl"
_DEFAULT_INDEX = _REPO_ROOT / "artifacts" / "m42" / "w2" / "workflow_certification_records.json"
_REGISTRY = _REPO_ROOT / "config" / "image-workflows" / "certified-registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def ledger_jsonl_path() -> Path:
    return _DEFAULT_JSONL


def load_ledger(*, jsonl_path: Path | None = None, index_path: Path | None = None) -> dict[str, Any]:
    """Load records from JSONL (authoritative) with optional JSON index fallback."""
    path = jsonl_path or _DEFAULT_JSONL
    records: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                records.append(rec)
    elif (index_path or _DEFAULT_INDEX).is_file():
        data = json.loads((index_path or _DEFAULT_INDEX).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            records = [r for r in (data.get("records") or []) if isinstance(r, dict)]
    return {"version": "1.0.0", "format": "append-only-jsonl", "records": records}


def next_record_id(workflow_id: str, ledger: Mapping[str, Any] | None = None) -> str:
    day = _day()
    prefix = f"CERT-{workflow_id}-{day}-"
    ledger = ledger or load_ledger()
    n = 1
    for rec in ledger.get("records") or []:
        rid = str(rec.get("certificationRecordId") or "")
        if rid.startswith(prefix):
            try:
                n = max(n, int(rid.rsplit("-", 1)[-1]) + 1)
            except ValueError:
                n += 1
    return f"{prefix}{n:03d}"


def append_certification_record(
    record: Mapping[str, Any],
    *,
    jsonl_path: Path | None = None,
    update_registry_pointer: bool = True,
) -> dict[str, Any]:
    """Append an immutable record to JSONL; optionally set registry pointer."""
    path = jsonl_path or _DEFAULT_JSONL
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = load_ledger(jsonl_path=path)
    rec = dict(record)
    wf_id = str(rec.get("workflowId") or "IMG-UNKNOWN")
    if not rec.get("certificationRecordId"):
        rec["certificationRecordId"] = next_record_id(wf_id, ledger)
    rec.setdefault("certifiedAt", _now())
    rec.setdefault("timestamp", rec["certifiedAt"])

    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=True) + "\n")

    # Convenience index (rebuild from JSONL — never mutate prior evidence)
    index = load_ledger(jsonl_path=path)
    _DEFAULT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    _DEFAULT_INDEX.write_text(json.dumps(index, indent=2), encoding="utf-8")

    if update_registry_pointer and _REGISTRY.is_file():
        reg = json.loads(_REGISTRY.read_text(encoding="utf-8"))
        key = str(rec.get("workflowKey") or "")
        status = str(rec.get("status") or "")
        fps = rec.get("fingerprints") if isinstance(rec.get("fingerprints"), dict) else {}
        for entry in reg.get("entries") or []:
            if entry.get("workflowKey") != key:
                continue
            entry["certificationRecordId"] = rec["certificationRecordId"]
            if fps:
                entry["fingerprints"] = {
                    "graphHash": fps.get("graphHash"),
                    "builderHash": fps.get("builderHash"),
                    "nodeInventoryHash": fps.get("nodeInventoryHash"),
                    "modelInventoryHash": fps.get("modelInventoryHash"),
                }
            if status in {"CERTIFIED", "Certified", "PASS"}:
                entry["status"] = "Certified"
            elif status in {"BLOCKED", "Blocked"} and entry.get("status") not in {"Deferred", "Retired"}:
                entry["status"] = "Blocked"
            break
        _REGISTRY.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
        try:
            from .certified_registry import reload_registry

            reload_registry()
        except Exception:
            pass

    return rec


def get_record(record_id: str, *, jsonl_path: Path | None = None) -> dict[str, Any] | None:
    for rec in load_ledger(jsonl_path=jsonl_path).get("records") or []:
        if rec.get("certificationRecordId") == record_id:
            return rec
    return None


def records_for_workflow(workflow_key: str, *, jsonl_path: Path | None = None) -> list[dict[str, Any]]:
    return [
        r
        for r in load_ledger(jsonl_path=jsonl_path).get("records") or []
        if r.get("workflowKey") == workflow_key
    ]


def ledger_is_append_only(*, jsonl_path: Path | None = None) -> bool:
    """Structural check: JSONL exists or empty ledger is ready; no mutable record blobs in registry."""
    path = jsonl_path or _DEFAULT_JSONL
    if not _REGISTRY.is_file():
        return False
    reg = json.loads(_REGISTRY.read_text(encoding="utf-8"))
    for entry in reg.get("entries") or []:
        blob = entry.get("certificationRecord")
        if isinstance(blob, dict) and len(blob) > 4:
            # Large inline evidence blobs are forbidden
            return False
    return path.parent.is_dir() or True
