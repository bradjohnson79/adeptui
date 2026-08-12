"""Append-only Certification Record ledger (M41 4.1B-L)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_LEDGER = _REPO_ROOT / "artifacts" / "m41" / "41bl" / "workflow_certification_records.json"
_REGISTRY = _REPO_ROOT / "config" / "video-workflows" / "certified-registry.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def load_ledger(path: Path | None = None) -> dict[str, Any]:
    ledger_path = path or _DEFAULT_LEDGER
    if not ledger_path.is_file():
        return {"version": "1.0.0", "records": []}
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"version": "1.0.0", "records": []}
    data.setdefault("records", [])
    return data


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
    ledger_path: Path | None = None,
    update_registry_pointer: bool = True,
) -> dict[str, Any]:
    """Append an immutable record; optionally set registry certificationRecordId pointer."""
    path = ledger_path or _DEFAULT_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = load_ledger(path)
    rec = dict(record)
    wf_id = str(rec.get("workflowId") or "WF-UNKNOWN")
    if not rec.get("certificationRecordId"):
        rec["certificationRecordId"] = next_record_id(wf_id, ledger)
    rec.setdefault("certifiedAt", _now())
    ledger.setdefault("records", []).append(rec)
    path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    # Also append JSONL for true append-only audit
    jsonl = path.with_suffix(".jsonl")
    with jsonl.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=True) + "\n")

    if update_registry_pointer and _REGISTRY.is_file():
        reg = json.loads(_REGISTRY.read_text(encoding="utf-8"))
        key = str(rec.get("workflowKey") or "")
        status = str(rec.get("status") or "")
        for entry in reg.get("entries") or []:
            if entry.get("workflowKey") != key:
                continue
            entry["certificationRecordId"] = rec["certificationRecordId"]
            # Drop inline blob if present — pointer is authoritative
            if "certificationRecord" in entry and isinstance(entry.get("certificationRecord"), dict):
                # Keep a thin summary for diagnostics only
                entry["certificationRecord"] = {
                    "certificationRecordId": rec["certificationRecordId"],
                    "status": status,
                    "certifiedAt": rec.get("certifiedAt"),
                }
            if status == "CERTIFIED":
                entry["status"] = "Certified"
            elif status == "BLOCKED" and entry.get("status") not in {"Deferred", "Retired"}:
                entry["status"] = "Blocked"
            break
        _REGISTRY.write_text(json.dumps(reg, indent=2), encoding="utf-8")
        try:
            from .certified_registry import reload_registry

            reload_registry()
        except Exception:
            pass

    return rec


def get_record(record_id: str, *, ledger_path: Path | None = None) -> dict[str, Any] | None:
    for rec in load_ledger(ledger_path).get("records") or []:
        if rec.get("certificationRecordId") == record_id:
            return rec
    return None
