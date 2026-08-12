from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_beta_runtime() -> tuple[Path, Path]:
    from scripts.beta_runtime.envutil import load_beta_env, resolve_data_dir

    load_beta_env(ROOT)
    data_dir = resolve_data_dir("data", ROOT)
    live_data_dir = resolve_data_dir(None, ROOT)
    return live_data_dir, live_data_dir / "studio.db"


def require_safe_environment(env_name: str, data_dir: Path, db_path: Path) -> None:
    if env_name != "beta-local":
        raise SystemExit(f"Refusing reset: expected --environment beta-local, got {env_name!r}.")
    if not db_path.is_file():
        raise SystemExit(f"Refusing reset: database not found at {db_path}.")
    if db_path.suffix.lower() != ".db":
        raise SystemExit(f"Refusing reset: expected a local sqlite .db file, got {db_path}.")
    try:
        db_path.resolve().relative_to(ROOT.resolve())
        data_dir.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"Refusing reset: DB/data path is outside repo root: {db_path}") from exc


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def table_columns(con: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
    return {t: [row[1] for row in con.execute(f'pragma table_info("{t}")').fetchall()] for t in tables}


def fetch_projects(con: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in con.execute("select id, name, created_at, updated_at from projects order by updated_at desc")]


def collect_owned_ids(con: sqlite3.Connection) -> dict[str, set[str]]:
    ids: dict[str, set[str]] = {}

    def collect(table: str, column: str, key: str, parent_ids: set[str] | None = None, parent_column: str = "project_id") -> set[str]:
        cols = [row[1] for row in con.execute(f'pragma table_info("{table}")').fetchall()]
        if table not in [r[0] for r in con.execute("select name from sqlite_master where type='table'")]:
            return set()
        if column not in cols:
            return set()
        if parent_ids is None:
            rows = con.execute(f'select "{column}" from "{table}" where "{column}" is not null').fetchall()
        else:
            if parent_column not in cols or not parent_ids:
                return set()
            marks = ",".join("?" for _ in parent_ids)
            rows = con.execute(
                f'select "{column}" from "{table}" where "{parent_column}" in ({marks}) and "{column}" is not null',
                tuple(parent_ids),
            ).fetchall()
        out = {str(r[0]) for r in rows if r[0]}
        ids[key] = out
        return out

    project_ids = {p["id"] for p in fetch_projects(con)}
    ids["project"] = project_ids
    collect("scenes", "id", "scene", project_ids)
    collect("assets", "id", "asset", project_ids)
    collect("jobs", "id", "job", project_ids)
    collect("production_bibles", "id", "bible", project_ids)
    collect("production_bible_versions", "id", "version", ids.get("bible", set()), "bible_id")
    collect("codirector_proposals", "id", "proposal", project_ids)
    return ids


def delete_owned_rows(con: sqlite3.Connection, ids: dict[str, set[str]]) -> dict[str, int]:
    columns = table_columns(con)
    deleted: dict[str, int] = {}
    version_columns = {"version_id", "based_on_version_id", "current_version_id", "resulting_version_id"}
    pk_map = {
        "project_id": ids.get("project", set()),
        "scene_id": ids.get("scene", set()),
        "asset_id": ids.get("asset", set()),
        "job_id": ids.get("job", set()),
        "proposal_id": ids.get("proposal", set()),
        "bible_id": ids.get("bible", set()),
    }

    ordered_tables = [
        t for t in columns if t != "projects"
    ] + ["projects"]
    for table in ordered_tables:
        clauses: list[str] = []
        params: list[str] = []
        cols = set(columns[table])
        for col, owned in pk_map.items():
            if col in cols and owned:
                clauses.append(f'"{col}" in ({",".join("?" for _ in owned)})')
                params.extend(sorted(owned))
        for col in version_columns:
            owned = ids.get("version", set())
            if col in cols and owned:
                clauses.append(f'"{col}" in ({",".join("?" for _ in owned)})')
                params.extend(sorted(owned))
        if table == "projects" and ids.get("project"):
            clauses = [f'"id" in ({",".join("?" for _ in ids["project"])})']
            params = sorted(ids["project"])
        elif table == "production_bible_versions" and ids.get("bible"):
            clauses.append(f'"bible_id" in ({",".join("?" for _ in ids["bible"])})')
            params.extend(sorted(ids["bible"]))
        elif table == "production_bibles" and ids.get("project"):
            clauses.append(f'"project_id" in ({",".join("?" for _ in ids["project"])})')
            params.extend(sorted(ids["project"]))
        if not clauses:
            continue
        before = con.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {" OR ".join(clauses)}', tuple(params)).fetchone()[0]
        if before:
            con.execute(f'DELETE FROM "{table}" WHERE {" OR ".join(clauses)}', tuple(params))
            deleted[table] = int(before)
    return deleted


def delete_fk_violations(con: sqlite3.Connection, deleted: dict[str, int], *, max_passes: int = 20) -> int:
    total = 0
    for _ in range(max_passes):
        issues = con.execute("pragma foreign_key_check").fetchall()
        if not issues:
            return total
        for table, rowid, _parent, _fkid in issues:
            if table == "projects":
                continue
            con.execute(f'DELETE FROM "{table}" WHERE rowid = ?', (rowid,))
            deleted[table] = deleted.get(table, 0) + 1
            total += 1
    return total


def backup_state(data_dir: Path, db_path: Path, projects: list[dict[str, Any]]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    backup_dir = ROOT / "backups" / f"pre-codirector-beta-reset-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup_dir / "studio.db")
    manifest = {"database": str(db_path), "dataDir": str(data_dir), "projectCount": len(projects), "projects": projects}
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    project_dirs = backup_dir / "projects"
    project_dirs.mkdir(exist_ok=True)
    for project in projects:
        for rel in (Path("projects") / project["id"], Path("assets") / project["id"]):
            src = data_dir / rel
            if src.exists():
                dst = project_dirs / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
    return backup_dir


def count_projects(con: sqlite3.Connection) -> int:
    return int(con.execute("select count(*) from projects").fetchone()[0])


def count_orphans(con: sqlite3.Connection) -> int:
    rows = con.execute("pragma foreign_key_check").fetchall()
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely reset local beta project data.")
    parser.add_argument("--environment", required=True)
    parser.add_argument("--backup", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-delete-all-projects", action="store_true")
    args = parser.parse_args()

    data_dir, db_path = load_beta_runtime()
    require_safe_environment(args.environment, data_dir, db_path)

    with connect(db_path) as con:
        projects = fetch_projects(con)
        ids = collect_owned_ids(con)
        delete_plan = {
            "engine": "sqlite",
            "environment": args.environment,
            "database": str(db_path),
            "dataDir": str(data_dir),
            "projectCount": len(projects),
            "projects": projects,
            "ownedIds": {k: sorted(v) for k, v in ids.items()},
        }
        if args.dry_run:
            print(json.dumps({"ok": True, "dryRun": True, **delete_plan}, indent=2, default=str))
            return 0
        if not args.confirm_delete_all_projects:
            raise SystemExit("Refusing reset: pass --confirm-delete-all-projects to perform deletion.")

        backup_dir = backup_state(data_dir, db_path, projects)
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN")
        deleted = delete_owned_rows(con, ids)
        fk_repairs = delete_fk_violations(con, deleted)
        con.commit()
        con.execute("PRAGMA foreign_keys=ON")
        post_projects = count_projects(con)
        orphan_count = count_orphans(con)
        print(
            json.dumps(
                {
                    "ok": True,
                    "environment": args.environment,
                    "database": str(db_path),
                    "backupPath": str(backup_dir),
                    "deletedProjects": projects,
                    "deletedTableCounts": deleted,
                    "fkRepairDeletes": fk_repairs,
                    "postResetProjectCount": post_projects,
                    "orphanForeignKeys": orphan_count,
                },
                indent=2,
                default=str,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
