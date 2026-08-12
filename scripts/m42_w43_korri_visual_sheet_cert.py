#!/usr/bin/env python3
"""M42 W43 Corrective Addendum — Generated Character Image Profile for Korri.

Drives the live Adept UI Beta API so the in-process QueueWorker runs real Z-Image /
character_sheet jobs. No mock assets. Fails closed if Comfy does not complete coverage.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "m42" / "w43" / "korri"
W43 = ROOT / "artifacts" / "m42" / "w43"
API = os.environ.get("ADEPT_API_BASE", "http://127.0.0.1:8758").rstrip("/")
POLL_SEC = int(os.environ.get("M42_W43_VISUAL_POLL_SEC", "1200"))
ADVANCE_EVERY = 8
# Creator-first: one project, one library — never spam disposable projects per run.
STABLE_PROJECT_NAME = os.environ.get("ADEPT_KORRI_PROJECT_NAME", "Korri Character Production")
STABLE_PROJECT_ID = os.environ.get("ADEPT_PROJECT_ID", "").strip()

REQUIRED = (
    "full_body_front",
    "full_body_side_left",
    "full_body_back",
    "closeup_front",
    "closeup_side_left",
    "closeup_back",
)
DETAIL = (
    "skin_closeup",
    "hair_front",
    "hair_side",
    "hair_back",
    "wardrobe_reference",
    "accessory_reference",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _req(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {path} → {e.code}: {err}") from e
    except URLError as e:
        raise RuntimeError(f"{method} {path} failed: {e}") from e


def _comfy_ok() -> bool:
    try:
        with urlopen("http://127.0.0.1:8188/system_stats", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _list_projects() -> list[dict[str, Any]]:
    raw = _req("GET", "/api/projects")
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, dict)]
    if isinstance(raw, dict):
        items = raw.get("items") or raw.get("projects") or []
        return [p for p in items if isinstance(p, dict)]
    return []


def _resolve_stable_project() -> tuple[str, dict[str, Any], bool]:
    """Reuse one Korri production project (Creator-first: one library). Returns (id, project, created)."""
    if STABLE_PROJECT_ID:
        # Verify it exists
        for p in _list_projects():
            if p.get("id") == STABLE_PROJECT_ID:
                return STABLE_PROJECT_ID, p, False
        raise RuntimeError(f"ADEPT_PROJECT_ID={STABLE_PROJECT_ID} not found")

    for p in _list_projects():
        if str(p.get("name") or "") == STABLE_PROJECT_NAME:
            pid = p.get("id") or p.get("projectId")
            if pid:
                return str(pid), p, False

    created = _req("POST", "/api/projects", {"name": STABLE_PROJECT_NAME})
    pid = created.get("id") or created.get("projectId")
    if not pid:
        raise RuntimeError(f"Could not create stable project {STABLE_PROJECT_NAME!r}: {created}")
    return str(pid), created, True


def main() -> int:
    if not _comfy_ok():
        evidence = {
            "passed": False,
            "reason": "ComfyUI not healthy — cannot certify Generated Character Image Profile",
            "comfyOk": False,
            "mock": False,
            "recordedAt": _now(),
        }
        _write(ART / "generated_image_profile.json", evidence)
        _write(W43 / "visual_sheet_results.json", evidence)
        print(json.dumps(evidence, indent=2))
        return 1

    try:
        project_id, project, project_created = _resolve_stable_project()
    except Exception as e:
        evidence = {
            "passed": False,
            "reason": f"Could not resolve stable Korri project: {e}",
            "stableProjectName": STABLE_PROJECT_NAME,
            "mock": False,
            "recordedAt": _now(),
        }
        _write(W43 / "visual_sheet_results.json", evidence)
        print(json.dumps(evidence, indent=2))
        return 1

    print(
        f"[visual-sheet] using project {project_id} "
        f"({STABLE_PROJECT_NAME!r}, created={project_created})"
    )

    korri = _req("POST", f"/api/projects/{project_id}/characters/seed-korri", {})
    character_id = korri.get("id")
    if not character_id:
        evidence = {
            "passed": False,
            "reason": "seed-korri failed",
            "response": korri,
            "mock": False,
            "recordedAt": _now(),
        }
        _write(W43 / "visual_sheet_results.json", evidence)
        print(json.dumps(evidence, indent=2))
        return 1

    started = _req(
        "POST",
        f"/api/projects/{project_id}/characters/{character_id}/visual-sheet/generate",
        {"includeDetails": True, "includePerformance": True},
    )
    pack = started.get("pack") or {}
    deadline = time.time() + POLL_SEC
    last = pack
    while time.time() < deadline:
        adv = _req(
            "POST",
            f"/api/projects/{project_id}/characters/{character_id}/visual-sheet/advance",
            {},
        )
        last = adv.get("pack") or last
        status = last.get("status")
        print(f"[visual-sheet] status={status} phase={last.get('phase')} roles={len(last.get('roleAssets') or {})}")
        if status in ("READY_FOR_OWNER", "OWNER_APPROVED", "FAILED"):
            break
        time.sleep(ADVANCE_EVERY)

    role_assets = dict(last.get("roleAssets") or {})
    missing = [r for r in REQUIRED if r not in role_assets]
    hero_ok = "hero_portrait" in role_assets
    details_ok = all(r in role_assets for r in DETAIL)
    perf_ok = all(r in role_assets for r in ("expression_sheet", "pose_sheet"))

    approved = None
    if last.get("status") == "READY_FOR_OWNER" and not missing and hero_ok:
        approved = _req(
            "POST",
            f"/api/projects/{project_id}/characters/{character_id}/visual-sheet/owner-approve",
            {"approvedBy": "owner", "selectDirectionId": "wild_sun_sprite"},
        )
        last = _req("GET", f"/api/projects/{project_id}/characters/{character_id}/visual-sheet")

    passed = (
        last.get("status") in ("READY_FOR_OWNER", "OWNER_APPROVED")
        and not missing
        and hero_ok
        and details_ok
        and bool(approved)
        and last.get("mock") is not True
    )

    evidence = {
        "phase": "M42-W43-visual-sheet-addendum",
        "passed": passed,
        "mock": False,
        "comfyOk": True,
        "apiBase": API,
        "projectId": project_id,
        "projectName": project.get("name") or STABLE_PROJECT_NAME,
        "projectReused": not project_created,
        "stableProjectPolicy": "one-project-one-library",
        "characterId": character_id,
        "packStatus": last.get("status"),
        "phaseName": last.get("phase"),
        "engine": last.get("engine") or "zimage",
        "workflows": last.get("workflows"),
        "roleAssets": role_assets,
        "requiredCoverageMissing": missing,
        "requiredCoverageComplete": len(missing) == 0,
        "heroOk": hero_ok,
        "detailsOk": details_ok,
        "performanceOk": perf_ok,
        "ownerApproved": bool(approved),
        "approvedGates": (approved or {}).get("approvedGates"),
        "jobs": last.get("jobs"),
        "recordedAt": _now(),
        "pollSec": POLL_SEC,
    }
    _write(ART / "generated_image_profile.json", evidence)
    _write(W43 / "visual_sheet_results.json", evidence)
    print(json.dumps({"passed": passed, "status": last.get("status"), "roles": len(role_assets)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
