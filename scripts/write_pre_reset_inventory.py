"""Emit the pre-reset creator-data inventory as JSON.

Reads the live studio.db (Beta stopped) and the project-id-keyed data dirs,
producing docs/release-gate/clean-beta-baseline/pre_reset_inventory.json.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
DB = DATA / "studio.db"
OUT = REPO_ROOT / "docs" / "release-gate" / "clean-beta-baseline" / "pre_reset_inventory.json"

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
    "timeline_retakes",
    "exports",
]


def _dir_count(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(1 for _ in p.iterdir())


def _dir_size_mb(p: Path) -> float:
    if not p.exists():
        return 0.0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6


def main() -> int:
    db = sqlite3.connect(DB)
    table_counts: dict[str, int] = {}
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        try:
            table_counts[name] = db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        except Exception:
            table_counts[name] = -1

    projects = [
        {"id": r[0], "name": r[1]}
        for r in db.execute("SELECT id, name FROM projects ORDER BY name").fetchall()
    ]
    jobs = [
        {"id": r[0], "project_id": r[1], "scene_id": r[2], "kind": r[3], "status": r[4]}
        for r in db.execute(
            "SELECT id, project_id, scene_id, kind, status FROM jobs ORDER BY created_at"
        ).fetchall()
    ]

    disk_inventory = {
        name: {"entries": _dir_count(DATA / name), "size_mb": round(_dir_size_mb(DATA / name), 2)}
        for name in PROJECT_KEYED_DIRS
    }

    payload = {
        "captured_utc": datetime.utcnow().isoformat() + "Z",
        "db_path": str(DB),
        "table_counts": table_counts,
        "project_count": len(projects),
        "projects": projects,
        "jobs": jobs,
        "disk_inventory": disk_inventory,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[inventory] -> {OUT}")
    print(f"[inventory] projects={len(projects)} jobs={len(jobs)} tables={len(table_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
