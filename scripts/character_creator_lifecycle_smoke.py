"""Save / Reset / Delete smoke against Schnick Coffee when Studio API is live.

Reset is a frontend snapshot restore (no PATCH). This smoke proves:
Save persists, GET after Save matches, Delete 404s, Korri is protected.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

API = "http://127.0.0.1:8758"
PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278"
KORRI_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b"


def _req(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if payload is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read().decode("utf-8") or "{}"
            return res.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"detail": raw}
        return exc.code, parsed


def main() -> int:
    try:
        health_status, _ = _req("GET", "/api/health")
    except Exception as exc:
        print(json.dumps({"blocker": f"Studio API unreachable: {exc}"}))
        print("FAIL — CHARACTER CREATOR SAVE/RESET/DELETE SMOKE")
        return 1
    if health_status >= 400:
        print(json.dumps({"blocker": f"health={health_status}"}))
        print("FAIL — CHARACTER CREATOR SAVE/RESET/DELETE SMOKE")
        return 1

    name = f"Lifecycle Smoke {int(time.time())}"
    created_status, created = _req(
        "POST",
        f"/api/projects/{PROJECT_ID}/characters",
        {
            "name": name,
            "description": "Disposable Schnick Coffee lifecycle fixture.",
        },
    )
    cid = str(created.get("id") or created.get("characterId") or "")
    report = {
        "create_status": created_status,
        "character_id": cid,
        "project_id": PROJECT_ID,
    }
    if created_status >= 400 or not cid:
        print(json.dumps(report, indent=2))
        print("FAIL — CHARACTER CREATOR SAVE/RESET/DELETE SMOKE")
        return 1

    saved_status, saved = _req(
        "PATCH",
        f"/api/projects/{PROJECT_ID}/characters/{cid}",
        {"description": "Persisted after Save."},
    )
    get_status, got = _req("GET", f"/api/projects/{PROJECT_ID}/characters/{cid}")
    korri_del_status, _ = _req("DELETE", f"/api/projects/{PROJECT_ID}/characters/{KORRI_ID}")
    del_status, _ = _req("DELETE", f"/api/projects/{PROJECT_ID}/characters/{cid}")
    gone_status, _ = _req("GET", f"/api/projects/{PROJECT_ID}/characters/{cid}")
    report.update(
        {
            "save_status": saved_status,
            "saved_description": saved.get("description"),
            "reload_description": got.get("description"),
            "get_status": get_status,
            "korri_delete_status": korri_del_status,
            "delete_status": del_status,
            "gone_status": gone_status,
            "reset_is_frontend_only": True,
        }
    )
    print(json.dumps(report, indent=2))
    ok = (
        saved_status < 400
        and get_status < 400
        and got.get("description") == "Persisted after Save."
        and korri_del_status in {403, 409}
        and del_status < 400
        and gone_status == 404
    )
    print("PASS — CHARACTER CREATOR SAVE/RESET/DELETE SMOKE" if ok else "FAIL — lifecycle smoke")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
