"""Register the already-rendered M3.0a fal artifact as a project Asset. No fal submission.

The live proof in `artifacts/m30a-fal/` cost real money once. This script makes that same file
usable inside the app - a `video` Asset carrying the fal provenance (model, request id, seed,
sha256) - without touching the fal API at all. The digest recorded in `live_proof_summary.json`
is re-computed before anything is written, so a corrupted or swapped file is refused rather
than registered under a request id it does not belong to.

Usage:
  python scripts/m30_register_fal_artifact.py --project-id <id>
  python scripts/m30_register_fal_artifact.py --list-projects
  python scripts/m30_register_fal_artifact.py            # newest project
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "studio-api"))

from app.config import settings  # noqa: E402
from app.db import Asset, Project, SessionLocal, init_db  # noqa: E402

ARTIFACT_DIR = REPO_ROOT / "artifacts" / "m30a-fal"
VIDEO_PATH = ARTIFACT_DIR / "seedance_t2v_4s_480p.mp4"
SUMMARY_PATH = ARTIFACT_DIR / "live_proof_summary.json"
ASSET_TAG = "m30a-fal-live-proof"


def say(msg: str) -> None:
    print(f"[m30-fal-register] {msg}", flush=True)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_summary() -> dict[str, Any]:
    if not SUMMARY_PATH.exists():
        raise SystemExit(f"missing proof summary: {SUMMARY_PATH}")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if summary.get("outcome") != "verified":
        raise SystemExit(f"proof summary outcome is {summary.get('outcome')!r}, expected 'verified'")
    return summary


def build_provenance(summary: dict[str, Any], digest: str) -> dict[str, Any]:
    """Secret-free provenance stored on the Asset row."""
    return {
        "source": "fal.ai live render (M3.0a budgeted proof)",
        "reused_existing_artifact": True,
        "resubmitted": False,
        "engine": summary.get("engine"),
        "provider": "fal",
        "model_id": summary.get("model_id"),
        "request_id": summary.get("request_id"),
        "seed": summary.get("seed"),
        "duration_sec": summary.get("duration_sec"),
        "resolution": summary.get("resolution"),
        "aspect_ratio": summary.get("aspect_ratio"),
        "prompt": summary.get("prompt"),
        "sha256": digest,
        "file_size_bytes": summary.get("file_size_bytes"),
        "rendered_utc": summary.get("completed_utc"),
        "artifact_path": summary.get("artifact_path"),
        "registered_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def existing_registration(db, project_id: str, request_id: str) -> Asset | None:
    rows = db.query(Asset).filter(Asset.project_id == project_id, Asset.tag == ASSET_TAG).all()
    for row in rows:
        try:
            meta = json.loads(row.prompt_meta_json or "{}")
        except json.JSONDecodeError:
            continue
        if meta.get("request_id") == request_id:
            return row
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", help="target project; defaults to the newest project")
    parser.add_argument("--list-projects", action="store_true", help="print project ids and exit")
    parser.add_argument("--force", action="store_true", help="register again even if already present")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        if args.list_projects:
            for project in db.query(Project).order_by(Project.created_at.desc()).all():
                say(f"{project.id}  {project.name}")
            return 0

        if args.project_id:
            project = db.get(Project, args.project_id)
            if project is None:
                say(f"no such project: {args.project_id}")
                return 2
        else:
            project = db.query(Project).order_by(Project.created_at.desc()).first()
            if project is None:
                say("no projects exist yet - create one in the app, or pass --project-id")
                return 2
            say(f"defaulting to newest project {project.id} ({project.name})")

        if not VIDEO_PATH.exists():
            say(f"missing artifact: {VIDEO_PATH}")
            return 2

        summary = load_summary()
        digest = sha256_of(VIDEO_PATH)
        expected = summary.get("sha256")
        if expected and digest != expected:
            say("artifact digest does not match the recorded proof - refusing to register")
            say(f"  expected {expected}")
            say(f"  actual   {digest}")
            return 3

        request_id = summary.get("request_id") or ""
        already = existing_registration(db, project.id, request_id)
        if already is not None and not args.force:
            say(f"already registered as asset {already.id} (use --force to add another copy)")
            return 0

        asset_id = str(uuid.uuid4())
        dest_dir = settings.data_dir / "assets" / project.id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{asset_id}.mp4"
        shutil.copy2(VIDEO_PATH, dest)

        asset = Asset(
            id=asset_id,
            project_id=project.id,
            tag=ASSET_TAG,
            kind="video",
            filename=VIDEO_PATH.name,
            path=str(dest),
            labels_json=json.dumps(["fal", "seedance", "live-proof"]),
            prompt_meta_json=json.dumps(build_provenance(summary, digest)),
        )
        db.add(asset)
        db.commit()

        say(f"registered asset {asset_id} in project {project.id}")
        say(f"  request_id {request_id}")
        say(f"  file       {dest}")
        say("  no fal job was submitted")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
