"""Live sequential Qwen supplementary View A then View B.

Uses Adept Stability Cert + a copy of the SenseNova corridor master.
Does not mutate Korri / Schnick / Venture. Real qwen2512.ref only.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8758"
CERT_NAME = "Adept Stability Cert"
FORBIDDEN = {
    "2347bf46-3762-4763-86c5-4a6032522278",  # Schnick
    "c49371ed-ba6b-4c16-ba98-a8b28b72118b",  # Korri
}
SOURCE_CANDIDATES = [
    ROOT / "docs" / "release-gate" / "spatial-map" / "evidence" / "geometry_bakeoff" / "source.png",
    ROOT / "data" / "projects" / "0ffe56e2-0d54-4926-91bf-0f947898d02e" / "assets" / "imagegen_edit_57323ebc.png",
    ROOT / "data" / "projects" / "0ffe56e2-0d58-4926-91bf-0f947898d02e" / "assets" / "imagegen_edit_57323ebc.png",
]
ATLAS = ROOT / "docs" / "release-gate" / "spatial-map" / "evidence" / "geometry_bakeoff" / "moge2" / "plates" / "top_down_orthographic.png"
EVIDENCE = ROOT / "docs" / "release-gate" / "spatial-map" / "evidence" / "supplementary_views"
TIMEOUT_SEC = 22 * 60


def _json(method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    last_exc: Exception | None = None
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} -> {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_exc = exc
            time.sleep(2 + attempt)
    raise RuntimeError(f"{method} {path} failed after retries: {last_exc}") from last_exc


def _ensure_cert_project() -> str:
    rows = _json("GET", "/api/projects")
    items = rows if isinstance(rows, list) else rows.get("projects") or []
    for row in items:
        if str(row.get("name") or "") == CERT_NAME:
            pid = str(row.get("id") or "")
            if pid in FORBIDDEN:
                raise RuntimeError("Refusing forbidden production project.")
            return pid
    created = _json("POST", "/api/projects", {"name": CERT_NAME})
    pid = str(created.get("id") or created.get("projectId") or "")
    if not pid or pid in FORBIDDEN:
        raise RuntimeError("Failed to create Adept Stability Cert.")
    return pid


def _upload_master(project_id: str) -> str:
    source = next((p for p in SOURCE_CANDIDATES if p.is_file()), None)
    if source is None:
        raise RuntimeError("Corridor master PNG was not found.")
    dest = EVIDENCE / "live_master.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    boundary = "----adeptSupplementary"
    payload = bytearray()
    payload.extend(f"--{boundary}\r\n".encode())
    payload.extend(b'Content-Disposition: form-data; name="file"; filename="corridor_master.png"\r\n')
    payload.extend(b"Content-Type: image/png\r\n\r\n")
    payload.extend(dest.read_bytes())
    payload.extend(b"\r\n")
    payload.extend(f"--{boundary}\r\n".encode())
    payload.extend(b'Content-Disposition: form-data; name="tag"\r\n\r\nlocation_master\r\n')
    payload.extend(f"--{boundary}\r\n".encode())
    payload.extend(b'Content-Disposition: form-data; name="kind"\r\n\r\nimage\r\n')
    payload.extend(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"{API}/api/projects/{project_id}/assets",
        data=bytes(payload),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    asset_id = str(body.get("id") or "")
    if not asset_id:
        raise RuntimeError(f"Upload failed: {body}")
    return asset_id


def _wait_slot(project_id: str, map_id: str, slot: str) -> dict:
    key = "viewA" if slot == "A" else "viewB"
    deadline = time.time() + TIMEOUT_SEC
    last = {}
    while time.time() < deadline:
        last = _json("GET", f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views")
        rec = (last.get("state") or {}).get(key) or {}
        status = str(rec.get("status") or "")
        print(f"  {slot} status={status} promptId={rec.get('promptId') or ''} asset={rec.get('assetId') or ''}", flush=True)
        if status in {"READY", "FAILED", "REJECTED"}:
            return last
        time.sleep(8)
    raise TimeoutError(f"View {slot} did not finish within {TIMEOUT_SEC}s: {last}")


def finish_after_a(project_id: str, map_id: str, *, master_id: str, analyze_a: dict | None = None) -> int:
    after_a = _json("GET", f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views")
    view_a = (after_a.get("state") or {}).get("viewA") or {}
    if view_a.get("status") != "READY":
        after_a = _wait_slot(project_id, map_id, "A")
        view_a = (after_a.get("state") or {}).get("viewA") or {}
    if view_a.get("status") != "READY":
        (EVIDENCE / "live_cert.json").write_text(json.dumps({"ok": False, "afterA": after_a}, indent=2), encoding="utf-8")
        print("VIEW_A_FAILED", flush=True)
        return 2
    accepted_a = _json("POST", f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/A/accept")

    analyze_b = _json("POST", f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/analyze")
    print(f"analyze B={analyze_b}", flush=True)
    _json(
        "POST",
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/generate",
        {"slot": "B"},
        timeout=90,
    )
    after_b = _wait_slot(project_id, map_id, "B")
    view_b = (after_b.get("state") or {}).get("viewB") or {}
    if view_b.get("status") != "READY":
        (EVIDENCE / "live_cert.json").write_text(json.dumps({"ok": False, "afterB": after_b}, indent=2), encoding="utf-8")
        print("VIEW_B_FAILED", flush=True)
        return 3
    accepted_b = _json("POST", f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/B/accept")
    final = _json("GET", f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views")

    strip = _json(
        "POST",
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/owner-review-strip",
        {
            "outputDir": str(EVIDENCE),
            "atlasPath": str(ATLAS) if ATLAS.is_file() else "",
        },
        timeout=90,
    )
    contact = _json(
        "POST",
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/contact-sheet",
        {"outputDir": str(EVIDENCE)},
        timeout=90,
    )

    report = {
        "ok": True,
        "projectId": project_id,
        "mapId": map_id,
        "masterAssetId": master_id,
        "observedAssetIds": final.get("observedAssetIds"),
        "analyzeA": analyze_a,
        "analyzeB": analyze_b,
        "viewA": (final.get("state") or {}).get("viewA"),
        "viewB": (final.get("state") or {}).get("viewB"),
        "confidence": (final.get("state") or {}).get("confidence"),
        "references": final.get("references"),
        "ownerStrip": strip,
        "contactSheet": contact,
        "acceptedA": bool(((accepted_a.get("state") or {}).get("viewA") or {}).get("approvedForSpatialReasoning")),
        "acceptedB": bool(((accepted_b.get("state") or {}).get("viewB") or {}).get("approvedForSpatialReasoning")),
        "inferredPlusInferredNotObserved": True,
        "notGeometryEvidence": True,
        "workflowKey": "qwen2512.ref",
        "purpose": "environment_supplementary_view",
    }
    (EVIDENCE / "live_cert.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "mapId": map_id, "promptA": report["viewA"].get("promptId"), "promptB": report["viewB"].get("promptId")}, indent=2))
    return 0


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    resume_map = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    resume_master = (sys.argv[2] if len(sys.argv) > 2 else "").strip()
    project_id = _ensure_cert_project()
    print(f"project={project_id}", flush=True)
    if resume_map:
        master_id = resume_master or str(
            (_json("GET", f"/api/spatial-map/projects/{project_id}/maps/{resume_map}/supplementary-views").get("master") or {}).get("assetId") or ""
        )
        print(f"resume map={resume_map} master={master_id}", flush=True)
        return finish_after_a(project_id, resume_map, master_id=master_id)

    master_id = _upload_master(project_id)
    created = _json(
        "POST",
        f"/api/spatial-map/projects/{project_id}/maps",
        {
            "title": "Supplementary View Assist Cert",
            "backgroundAssetId": master_id,
            "originalEnvironmentReferenceAssetId": master_id,
            "masterEnvironmentPrompt": "metallic SenseNova corridor with elevators, repeating arches, and chamber openings",
        },
    )
    map_id = str((created.get("document") or {}).get("id") or "")
    if not map_id:
        raise RuntimeError(f"Map create failed: {created}")
    print(f"map={map_id} master={master_id}", flush=True)
    analyze_a = _json("POST", f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/analyze")
    print(f"analyze A={analyze_a}", flush=True)
    gen_a = _json(
        "POST",
        f"/api/spatial-map/projects/{project_id}/maps/{map_id}/supplementary-views/generate",
        {"slot": "A"},
        timeout=90,
    )
    print(f"queued A job={((gen_a.get('view') or {}).get('jobId'))}", flush=True)
    return finish_after_a(project_id, map_id, master_id=master_id, analyze_a=analyze_a)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "live_cert.json").write_text(json.dumps({"ok": False, "error": str(exc)}, indent=2), encoding="utf-8")
        print(f"FAILED {exc}", file=sys.stderr)
        raise
