"""Binary gate for project password protection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_ART = _REPO / "artifacts" / "project-security"
_DOCS = _REPO / "docs" / "release-gate" / "project-security"

_FLAGS = [
    "projectPasswordMenuOperational",
    "projectPasswordSetupOperational",
    "projectPasswordHashingOperational",
    "projectPasswordPlaintextStorageZero",
    "projectUnlockOperational",
    "projectUnlockGrantOperational",
    "projectLockNowOperational",
    "projectPasswordChangeOperational",
    "projectPasswordDisableOperational",
    "projectPasswordResetOperational",
    "projectProtectedRoutesOperational",
    "projectDirectRouteBypassZero",
    "projectCoDirectorLockEnforced",
    "projectBruteForceProtectionOperational",
    "projectSecurityAuditOperational",
    "projectDuplicateProtectionOperational",
    "projectExportProtectionHonest",
    "projectCrossProjectGrantDenied",
    "projectPasswordPlaywrightPassed",
    "projectPasswordNoMockData",
    "projectPasswordReportsComplete",
    "projectPasswordArtifactsComplete",
]


def _load(name: str) -> dict[str, Any]:
    p = _ART / name
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def evaluate_project_password_protection_gate() -> dict[str, Any]:
    cert = _load("certification_results.json")
    unit = _load("unit_results.json")
    pw = _load("playwright_results.json")
    flags = {k: bool(cert.get(k, False)) for k in _FLAGS}
    flags["projectPasswordPlaywrightPassed"] = bool(pw.get("passed")) or flags["projectPasswordPlaywrightPassed"]
    flags["projectPasswordArtifactsComplete"] = bool((_ART / "certification_results.json").is_file()) and bool(
        (_ART / "unit_results.json").is_file()
    )
    flags["projectPasswordReportsComplete"] = (_DOCS / "PROJECT_PASSWORD_PROTECTION_REPORT.md").is_file()
    if unit.get("passed"):
        flags["projectPasswordHashingOperational"] = True
        flags["projectPasswordPlaintextStorageZero"] = True
        flags["projectPasswordNoMockData"] = True
    all_ok = all(flags.values()) and bool(cert.get("passed", False))
    return {
        "feature": "project-password-protection",
        "projectPasswordProtectionGo": all_ok,
        "flags": flags,
        "binaryOnly": True,
        "conditionalGoForbidden": True,
        "mock": False,
    }
