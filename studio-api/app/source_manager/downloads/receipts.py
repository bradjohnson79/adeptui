"""Installation receipts and link records."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..models import strip_secrets
from .models import new_install_id, utc_now
from .persistence import get_receipt as _get_receipt
from .persistence import list_receipts, save_receipt


def get_receipt(install_id: str):
    return _get_receipt(install_id)


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"
    except OSError:
        return None


def build_managed_receipt(
    *,
    operation: dict[str, Any],
    destination_root: str | Path,
    files: list[dict[str, Any]],
    version: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    plan = operation.get("plan") or {}
    artifacts = []
    root = Path(destination_root)
    for item in files:
        rel = str(item.get("relativePath") or item.get("relative_path") or "")
        abs_path = root / rel if rel else None
        size = item.get("size")
        checksum = item.get("checksum")
        if abs_path and abs_path.is_file():
            if size is None:
                try:
                    size = abs_path.stat().st_size
                except OSError:
                    size = None
            if not checksum:
                checksum = _sha256_file(abs_path)
        artifacts.append(
            {
                "artifactId": item.get("artifactId") or item.get("artifact_id"),
                "relativePath": rel,
                "size": size,
                "checksum": checksum,
                "role": item.get("role"),
                "ownership": item.get("ownership") or "installed_by_adept",
            }
        )
    receipt = {
        "id": new_install_id(),
        "operationId": operation.get("id"),
        "installPlanId": operation.get("installPlanId") or plan.get("id"),
        "componentId": operation.get("componentId"),
        "sourceId": operation.get("sourceId"),
        "providerId": operation.get("providerId"),
        "version": version or plan.get("sourceRevision") or plan.get("metadata", {}).get("version"),
        "sourceRevision": plan.get("sourceRevision"),
        "sourceFingerprint": plan.get("sourceFingerprint"),
        "installedAt": utc_now(),
        "destinationRoot": str(destination_root),
        "managed": True,
        "kind": "managed_install",
        "artifacts": artifacts,
        "previousFiles": [],
        "warnings": list(warnings or []),
        "verification": {"status": "passed", "validatedAt": utc_now()},
        "rollbackAvailable": True,
    }
    return strip_secrets(receipt)


def build_link_record(
    *,
    component_id: str,
    linked_path: str,
    observed_files: list[dict[str, Any]] | None = None,
    verification_status: str = "passed",
    source_id: str | None = None,
) -> dict[str, Any]:
    return strip_secrets(
        {
            "id": new_install_id(),
            "operationId": None,
            "installPlanId": None,
            "componentId": component_id,
            "sourceId": source_id,
            "providerId": "existing_install",
            "version": None,
            "sourceRevision": None,
            "sourceFingerprint": None,
            "installedAt": utc_now(),
            "destinationRoot": linked_path,
            "managed": False,
            "kind": "linked_existing",
            "artifacts": list(observed_files or []),
            "previousFiles": [],
            "warnings": ["Rollback unavailable — this directory is not managed by Adept UI."],
            "verification": {"status": verification_status, "validatedAt": utc_now()},
            "rollbackAvailable": False,
        }
    )


def persist_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    return save_receipt(receipt)


def history_entries() -> list[dict[str, Any]]:
    items = list(list_receipts().values())
    items.sort(key=lambda r: str(r.get("installedAt") or ""), reverse=True)
    return [
        {
            "id": r.get("id"),
            "componentId": r.get("componentId"),
            "version": r.get("version"),
            "providerId": r.get("providerId"),
            "sourceId": r.get("sourceId"),
            "result": r.get("verification", {}).get("status") if isinstance(r.get("verification"), dict) else None,
            "installedAt": r.get("installedAt"),
            "destinationSummary": _summarize_path(str(r.get("destinationRoot") or "")),
            "managed": bool(r.get("managed")),
            "kind": r.get("kind"),
            "fileCount": len(r.get("artifacts") or []),
            "totalSize": sum(int(a.get("size") or 0) for a in (r.get("artifacts") or []) if isinstance(a, dict)),
            "verificationState": (
                r.get("verification", {}).get("status") if isinstance(r.get("verification"), dict) else None
            ),
            "rollbackAvailable": bool(r.get("rollbackAvailable")),
        }
        for r in items
    ]


def _summarize_path(path: str) -> str:
    if not path:
        return ""
    parts = Path(path).parts
    if len(parts) <= 3:
        return path
    return str(Path(*parts[-3:]))


def verify_receipt(install_id: str) -> dict[str, Any]:
    receipt = _get_receipt(install_id)
    if not receipt:
        raise KeyError(install_id)
    root = Path(str(receipt.get("destinationRoot") or ""))
    missing = []
    mismatched = []
    for art in receipt.get("artifacts") or []:
        if not isinstance(art, dict):
            continue
        rel = art.get("relativePath")
        if not rel:
            continue
        path = root / str(rel)
        if not path.is_file():
            missing.append(rel)
            continue
        expected = art.get("checksum")
        if expected and str(expected).startswith("sha256:"):
            actual = _sha256_file(path)
            if actual and actual != expected:
                mismatched.append(rel)
    status = "passed" if not missing and not mismatched else "failed"
    return {
        "installId": install_id,
        "status": status,
        "missing": missing,
        "checksumMismatch": mismatched,
        "validatedAt": utc_now(),
    }
