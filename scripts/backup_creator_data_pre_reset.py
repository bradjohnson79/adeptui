"""Pre-clean-beta-reset backup.

Copies studio.db and the project-id-keyed creator data directories into
data/backups/pre-clean-beta-reset_<timestamp>/, then verifies the backup DB
opens and reports the same project count as the source. Models, venvs,
runtimes, secrets, and app-level config are deliberately excluded.

Usage:
    python scripts/backup_creator_data_pre_reset.py
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
DB = DATA / "studio.db"

# Project-id-keyed creator data families. All entries are dev/orphan residue.
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


def _dir_size_mb(p: Path) -> float:
    if not p.exists():
        return 0.0
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6


def main() -> int:
    if not DB.exists():
        print(f"FATAL: {DB} not found", file=sys.stderr)
        return 2

    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
    dest = DATA / "backups" / f"pre-clean-beta-reset_{ts}"
    dest.mkdir(parents=True, exist_ok=True)

    # 1. Backup studio.db (file copy — Beta is stopped, no writers).
    db_dest = dest / "studio.db"
    shutil.copy2(DB, db_dest)
    print(f"[backup] studio.db -> {db_dest}")

    # 2. Backup project-keyed dirs.
    copied = []
    for name in PROJECT_KEYED_DIRS:
        src = DATA / name
        if not src.exists():
            print(f"[backup] skip (missing): {name}")
            continue
        dst = dest / name
        shutil.copytree(src, dst, dirs_exist_ok=True)
        copied.append((name, _dir_size_mb(src)))
        print(f"[backup] {name} -> {dst} ({copied[-1][1]:.1f} MB)")

    # 3. Verify backup DB opens and matches source project count.
    src_count = sqlite3.connect(DB).execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    dst_count = sqlite3.connect(db_dest).execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    if src_count != dst_count:
        print(f"FATAL: project count mismatch src={src_count} backup={dst_count}", file=sys.stderr)
        return 3
    print(f"[verify] backup db projects={dst_count} (matches source {src_count})")

    # 4. Write a small manifest.
    manifest = dest / "MANIFEST.txt"
    manifest.write_text(
        f"pre-clean-beta-reset backup\n"
        f"created_utc={ts}\n"
        f"source_db={DB}\n"
        f"projects_in_backup={dst_count}\n"
        f"copied_dirs:\n"
        + "".join(f"  - {n}: {s:.1f} MB\n" for n, s in copied),
        encoding="utf-8",
    )
    print(f"[backup] manifest -> {manifest}")
    print(f"[backup] DONE -> {dest}")
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
