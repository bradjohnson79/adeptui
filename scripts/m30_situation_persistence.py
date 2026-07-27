"""Durability check for the situation run: read the rows out of process, read-only.

The API keeps its own connection open, so this opens the same SQLite file in read-only mode
and confirms the situation rows are committed to disk rather than living in a session.
"""

from __future__ import annotations

import glob
import json
import os
import sqlite3
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "m30-situations"
DATA_DIR = Path(
    os.environ.get("STUDIO_DATA_DIR")
    or (Path.home() / "AppData" / "Local" / "Temp" / "adept-m30-sit-data")
)
DB = DATA_DIR / "studio.db"

con = sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)
con.row_factory = sqlite3.Row

report = {"database": str(DB), "situations": []}
for path in sorted(glob.glob(str(OUT / "situation-*-production.json"))):
    rec = json.loads(Path(path).read_text(encoding="utf-8"))
    pid = rec.get("projectId")
    sid = rec.get("sceneId")
    if not pid:
        continue
    assets = con.execute(
        "SELECT id, kind, tag, path FROM assets WHERE project_id = ?", (pid,)
    ).fetchall()
    scene = con.execute("SELECT director_json FROM scenes WHERE id = ?", (sid,)).fetchone()
    director = json.loads(scene["director_json"] or "{}") if scene else {}
    on_disk = []
    for row in assets:
        p = Path(row["path"]) if row["path"] else None
        on_disk.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "tag": row["tag"],
                "exists": bool(p and p.exists()),
                "bytes": p.stat().st_size if p and p.exists() else 0,
            }
        )
    report["situations"].append(
        {
            "n": rec["n"],
            "situation": rec["situation"],
            "projectId": pid,
            "assetRows": len(assets),
            "assetsOnDisk": sum(1 for a in on_disk if a["exists"]),
            "totalBytes": sum(a["bytes"] for a in on_disk),
            "assets": on_disk,
            "directorAudioClips": len(director.get("audio_clips") or []),
            "directorSfxClips": len(director.get("sfx_clips") or []),
            "directorImageClips": len(director.get("image_clips") or []),
        }
    )

counts = {
    "projects": con.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"],
    "assets": con.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"],
    "jobs": con.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"],
}
for table in ("m29_audio_cues", "m29_asset_versions", "m29_timeline_proposals",
              "m214_story_profiles", "m211_decision_records", "m211_execution_traces"):
    try:
        counts[table] = con.execute("SELECT COUNT(*) c FROM %s" % table).fetchone()["c"]
    except sqlite3.Error as exc:
        counts[table] = "unavailable: %s" % exc
report["rowCounts"] = counts
con.close()

(OUT / "persistence-check.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print(json.dumps(report["rowCounts"], indent=1))
for s in report["situations"]:
    print(
        "S%02d assets=%s onDisk=%s bytes=%s audio=%s sfx=%s image=%s"
        % (
            s["n"],
            s["assetRows"],
            s["assetsOnDisk"],
            s["totalBytes"],
            s["directorAudioClips"],
            s["directorSfxClips"],
            s["directorImageClips"],
        )
    )
