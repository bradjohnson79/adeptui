"""Clean creator data reset — authoritative deletion + orphan/disk cleanup + integrity gate.

Phases covered (per plan):
  Phase 2 step 6 — DELETE /api/projects/{id} for every project, with per-project
                    latency + API-error capture (deletion stress test).
  Phase 2 step 7 — orphan cleanup for rows whose owners are already gone
                    (asset_versions/edges, codirector_approvals/execution_receipts).
  Phase 2 step 8 — disk cleanup of project-id-keyed dirs + timeline_retakes + exports.
  Phase 2 step 9 — integrity gate: zero project-scoped rows, zero dangling refs,
                    app-level tables (schema_migrations, etc.) untouched.

Assumes Beta is running (started normally, no cert stub, no export env) so the
authoritative DELETE endpoint exercises the repaired cascade. The script does
NOT start/stop Beta itself.

Usage:
    python scripts/clean_creator_data_reset.py
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
DB = DATA / "studio.db"
OUT_DIR = REPO_ROOT / "docs" / "release-gate" / "clean-beta-baseline"
OUT_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = "http://127.0.0.1:8758/api"

# Project-id-keyed creator data families. Every UUID-named entry is dev/orphan
# residue and is removed. App-level files inside these dirs (if any) are
# preserved by skipping non-UUID entries.
PROJECT_KEYED_DIRS = [
    "projects",
    "assets",
    "audio_studio",
    "environment_reference_sheet",
    "image_pipeline",
    "image_product",
    "minimax_h3",
    "storyboard_studio",
    "visual_continuity",
]
# timeline_retakes holds id-keyed JSONs; exports holds dev export bundles.
EXTRA_CLEAN_DIRS = ["timeline_retakes", "exports"]

UUID_RE = __import__("re").compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", __import__("re").I
)


def _http_delete(project_id: str) -> tuple[int, str]:
    url = f"{API_BASE}/projects/{project_id}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        return e.code, body
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


def _delete_all_projects(projects: list[dict]) -> dict:
    """Return a metrics dict with per-project rows + summary."""
    rows = []
    ok = 0
    err = 0
    for p in projects:
        t0 = time.perf_counter()
        status, error = _http_delete(p["id"])
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        rows.append(
            {
                "project_id": p["id"],
                "name": p["name"],
                "elapsed_ms": elapsed_ms,
                "http_status": status,
                "error": error,
            }
        )
        if status == 200:
            ok += 1
        else:
            err += 1
        flag = "OK" if status == 200 else "ERR"
        print(f"[delete] {flag} {status} {elapsed_ms}ms {p['name']}")

    latencies = [r["elapsed_ms"] for r in rows]
    summary = {
        "total_ms": round(sum(latencies), 2),
        "count": len(rows),
        "ok_count": ok,
        "error_count": err,
        "p50_ms": round(statistics.median(latencies), 2) if latencies else 0,
        "p95_ms": round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 20 else round(max(latencies), 2) if latencies else 0,
        "max_ms": round(max(latencies), 2) if latencies else 0,
    }
    return {"rows": rows, "summary": summary}


def _orphan_cleanup(db: sqlite3.Connection) -> dict:
    """Delete rows whose owners are already gone (documented orphan cleanup).

    Two categories:
    1. Indirect orphans: asset_versions/edges and codirector_approvals/receipts
       whose parent asset/proposal no longer exists.
    2. Project-scoped orphans: rows in any table with project_id/projectId
       referencing a project that no longer exists (pre-existing orphans from
       projects deleted in prior dev sessions, which the authoritative DELETE
       of current projects cannot reach).
    """
    measures = {}
    # 1. Indirect orphans.
    measures["asset_versions_orphans"] = db.execute(
        "DELETE FROM asset_versions WHERE asset_id NOT IN (SELECT id FROM assets)"
    ).rowcount
    measures["asset_edges_orphans_from"] = db.execute(
        "DELETE FROM asset_edges WHERE from_id NOT IN (SELECT id FROM assets)"
    ).rowcount
    measures["asset_edges_orphans_to"] = db.execute(
        "DELETE FROM asset_edges WHERE to_id NOT IN (SELECT id FROM assets)"
    ).rowcount
    measures["codirector_approvals_orphans"] = db.execute(
        "DELETE FROM codirector_approvals WHERE proposal_id NOT IN (SELECT id FROM codirector_proposals)"
    ).rowcount
    measures["codirector_execution_receipts_orphans"] = db.execute(
        "DELETE FROM codirector_execution_receipts WHERE proposal_id NOT IN (SELECT id FROM codirector_proposals)"
    ).rowcount
    for k, v in measures.items():
        print(f"[orphan] {k}: {v}")

    # 2. Project-scoped orphans across ALL tables with project_id/projectId.
    table_names = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    project_scoped_removed = {}
    for t in table_names:
        if t == "projects":
            continue
        cols = [c[1] for c in db.execute(f"PRAGMA table_info({t})").fetchall()]
        col = None
        for c in ("project_id", "projectId"):
            if c in cols:
                col = c
                break
        if not col:
            continue
        qcol = f'"{col}"' if col == "projectId" else col
        n = db.execute(
            f"DELETE FROM {t} WHERE {qcol} NOT IN (SELECT id FROM projects)"
        ).rowcount
        if n > 0:
            project_scoped_removed[t] = n
            print(f"[orphan] project_scoped {t}: {n}")
    measures["project_scoped_total"] = sum(project_scoped_removed.values())
    measures["project_scoped_by_table"] = project_scoped_removed
    db.commit()
    return measures


def _disk_cleanup() -> dict:
    """Remove project-id-keyed dirs + timeline_retakes + exports dev residue."""
    removed = {}
    for name in PROJECT_KEYED_DIRS + EXTRA_CLEAN_DIRS:
        root = DATA / name
        if not root.exists():
            print(f"[disk] skip (missing): {name}")
            continue
        count = 0
        for entry in list(root.iterdir()):
            # Remove UUID-named entries (project-owned). For timeline_retakes
            # (id.json) and exports (named bundles), remove all entries since
            # they are all dev residue per the audit.
            if name in EXTRA_CLEAN_DIRS or UUID_RE.match(entry.name):
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    try:
                        entry.unlink()
                    except FileNotFoundError:
                        pass
                count += 1
        removed[name] = count
        print(f"[disk] {name}: removed {count} entries")
    return removed


def _integrity_gate(db: sqlite3.Connection) -> dict:
    """Assert zero project-scoped rows, zero dangling refs, app tables intact."""
    gate = {"passed": True, "checks": {}}

    def _check(name: str, sql: str, expected: int = 0) -> None:
        actual = db.execute(sql).fetchone()[0]
        ok = actual == expected
        gate["checks"][name] = {"actual": actual, "expected": expected, "ok": ok}
        if not ok:
            gate["passed"] = False
            print(f"[gate] FAIL {name}: {actual} != {expected}")
        else:
            print(f"[gate] ok   {name}: {actual}")

    # Core project-scoped tables must be empty.
    for t in ("projects", "scenes", "jobs", "assets", "character_profiles", "voice_profiles"):
        _check(f"{t}_empty", f"SELECT COUNT(*) FROM {t}")

    # Indirect tables that should now be empty after cascade + orphan cleanup.
    for t in ("asset_versions", "asset_edges", "codirector_approvals", "codirector_execution_receipts"):
        _check(f"{t}_empty", f"SELECT COUNT(*) FROM {t}")

    # Dangling reference checks.
    _check("dangling_scene_project", "SELECT COUNT(*) FROM scenes s LEFT JOIN projects p ON s.project_id = p.id WHERE p.id IS NULL")
    _check("dangling_job_project", "SELECT COUNT(*) FROM jobs j LEFT JOIN projects p ON j.project_id = p.id WHERE p.id IS NULL")
    _check("dangling_version_asset", "SELECT COUNT(*) FROM asset_versions v LEFT JOIN assets a ON v.asset_id = a.id WHERE a.id IS NULL")
    _check("dangling_edge_from", "SELECT COUNT(*) FROM asset_edges e LEFT JOIN assets a ON e.from_id = a.id WHERE a.id IS NULL")
    _check("dangling_edge_to", "SELECT COUNT(*) FROM asset_edges e LEFT JOIN assets a ON e.to_id = a.id WHERE a.id IS NULL")
    _check("dangling_approval_proposal", "SELECT COUNT(*) FROM codirector_approvals a LEFT JOIN codirector_proposals p ON a.proposal_id = p.id WHERE p.id IS NULL")
    _check("dangling_receipt_proposal", "SELECT COUNT(*) FROM codirector_execution_receipts r LEFT JOIN codirector_proposals p ON r.proposal_id = p.id WHERE p.id IS NULL")

    # App-level tables must be UNTOUCHED (record counts, don't assert zero).
    sm = db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    gate["checks"]["schema_migrations_present"] = {"actual": sm, "ok": sm > 0}
    if sm == 0:
        gate["passed"] = False
        print(f"[gate] FAIL schema_migrations_present: {sm}")
    else:
        print(f"[gate] ok   schema_migrations_present: {sm}")
    # Disk dirs must have zero UUID entries left.
    for name in PROJECT_KEYED_DIRS + EXTRA_CLEAN_DIRS:
        root = DATA / name
        leftover = 0
        if root.exists():
            for entry in root.iterdir():
                if name in EXTRA_CLEAN_DIRS or UUID_RE.match(entry.name):
                    leftover += 1
        _check(f"disk_{name}_clean", "SELECT 0" if leftover == 0 else "SELECT 1")
    return gate


def main() -> int:
    if not DB.exists():
        print(f"FATAL: {DB} not found", file=sys.stderr)
        return 2

    db = sqlite3.connect(DB)
    db.execute("PRAGMA foreign_keys = ON")

    projects = [
        {"id": r[0], "name": r[1]}
        for r in db.execute("SELECT id, name FROM projects ORDER BY name").fetchall()
    ]
    if not projects:
        print("[reset] no projects to delete; proceeding to orphan/disk cleanup")
    print(f"[reset] {len(projects)} projects to delete via authoritative path")

    # Step 6 — authoritative deletion with stress metrics.
    deletion = _delete_all_projects(projects)

    # Re-open DB to reflect deletions committed by the API process.
    db.close()
    db = sqlite3.connect(DB)
    db.execute("PRAGMA foreign_keys = ON")

    # Step 7 — orphan cleanup.
    orphans = _orphan_cleanup(db)

    # Step 8 — disk cleanup.
    disk = _disk_cleanup()

    # Step 9 — integrity gate.
    gate = _integrity_gate(db)
    db.close()

    # Write evidence.
    evidence = {
        "completed_utc": datetime.utcnow().isoformat() + "Z",
        "deletion": deletion,
        "orphan_cleanup": orphans,
        "disk_cleanup": disk,
        "integrity_gate": gate,
    }
    out = OUT_DIR / "reset_evidence.json"
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"[reset] evidence -> {out}")

    if not gate["passed"]:
        print("[reset] INTEGRITY GATE FAILED", file=sys.stderr)
        return 1
    print("[reset] INTEGRITY GATE PASSED")
    print("[reset] DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
