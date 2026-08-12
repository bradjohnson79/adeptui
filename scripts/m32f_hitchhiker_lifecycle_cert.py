"""M3.2f Hitchhiker production lifecycle certification (API + media probes)."""
from __future__ import annotations

import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
LTX_SCENE = "6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f"
IMAGE_A = "d523d406-ce9a-4073-87db-f5ddd06816d1"
DIALOGUE = "c5cdd736-8f89-42e3-a7a8-9cb97043bf8a"
ROOT = Path("artifacts/m32f/hitchhiker-production-lifecycle")
OUT = Path("artifacts/m32f/hitchhiker-production-certification.json")


def get(url: str):
    return json.load(urllib.request.urlopen(url, timeout=60))


def ffprobe(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file() or path.stat().st_size <= 0:
        return {"ok": False, "error": "missing_or_empty", "path": str(path)}
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size,format_name:stream=codec_type,codec_name,width,height",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(proc.stdout or "{}")
        streams = data.get("streams") or []
        fmt = data.get("format") or {}
        return {
            "ok": proc.returncode == 0 and bool(streams),
            "path": str(path),
            "size": path.stat().st_size,
            "duration": float(fmt.get("duration") or 0),
            "format": fmt.get("format_name"),
            "has_video": any(s.get("codec_type") == "video" for s in streams),
            "has_audio": any(s.get("codec_type") == "audio" for s in streams),
            "streams": streams,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "path": str(path)}


def asset_path(asset: dict) -> Path | None:
    for key in ("path", "localPath", "filePath", "uri"):
        value = asset.get(key)
        if value and Path(str(value)).is_file():
            return Path(str(value))
    return None


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "media-probes").mkdir(exist_ok=True)
    (ROOT / "lineage").mkdir(exist_ok=True)
    (ROOT / "01-project-load").mkdir(exist_ok=True)

    project = get(f"{API}/api/projects/{PID}")
    scenes = get(f"{API}/api/projects/{PID}/scenes")
    library = get(f"{API}/api/projects/{PID}/library")
    jobs = get(f"{API}/api/projects/{PID}/jobs")
    if isinstance(jobs, dict):
        jobs = jobs.get("items") or jobs.get("jobs") or []
    assets = project.get("assets") or library.get("assets") or library.get("items") or []
    if isinstance(library, list):
        assets = library
    if not isinstance(assets, list):
        assets = []

    (ROOT / "01-project-load" / "project.json").write_text(json.dumps(project, indent=2), encoding="utf-8")
    (ROOT / "01-project-load" / "scenes.json").write_text(json.dumps(scenes, indent=2), encoding="utf-8")

    by_id = {a.get("id"): a for a in assets if isinstance(a, dict)}
    image = by_id.get(IMAGE_A) or next((a for a in assets if str(a.get("kind") or a.get("type") or "").lower() in {"image", "still"}), None)
    dialogue = by_id.get(DIALOGUE)
    video_candidates = [
        a
        for a in assets
        if str(a.get("kind") or a.get("type") or "").lower() in {"video", "clip", "scene"}
        or str(a.get("path") or "").lower().endswith(".mp4")
    ]
    lipsync_path = Path(f"data/projects/{PID}/renders/scene_1_ab97e9e4_lipsync.mp4")
    export_dir = Path("data/exports/M3.0i_Hitchhiker_Native_Production_d1683511")

    probes = {
        "image_a": ffprobe(asset_path(image) or Path("missing")) if image else {"ok": False, "error": "missing_image"},
        "dialogue": ffprobe(asset_path(dialogue) or Path("missing")) if dialogue else {"ok": False, "error": "missing_dialogue"},
        "lipsync": ffprobe(lipsync_path),
    }
    playable_videos = []
    for asset in video_candidates:
        p = asset_path(asset)
        if not p:
            continue
        probe = ffprobe(p)
        if probe.get("ok") and probe.get("has_video"):
            playable_videos.append({"assetId": asset.get("id"), "probe": probe})
    probes["videos"] = playable_videos

    stuck = [
        j
        for j in jobs
        if str(j.get("status") or j.get("state") or "").lower() in {"queued", "running", "claimed"}
    ]
    lipsync_jobs = [
        j
        for j in jobs
        if "lipsync" in str(j.get("type") or j.get("kind") or j.get("message") or "").lower()
        or "lip" in str(j.get("type") or "").lower()
    ]

    export_ok = export_dir.is_dir() and (export_dir / "project.json").is_file()
    export_assets = list(export_dir.rglob("*")) if export_ok else []

    stages = {
        "project_load": bool(project.get("id") == PID),
        "scenes_present": isinstance(scenes, list) and len(scenes) > 0,
        "image_registered": bool(image),
        "image_playable": bool(probes["image_a"].get("ok")),
        "dialogue_registered": bool(dialogue),
        "dialogue_playable": bool(probes["dialogue"].get("ok") and probes["dialogue"].get("has_audio")),
        "video_playable": len(playable_videos) > 0,
        "lipsync_playable": bool(probes["lipsync"].get("ok") and probes["lipsync"].get("has_video") and probes["lipsync"].get("has_audio")),
        "export_pack": export_ok,
        "no_stuck_jobs": len(stuck) == 0,
        "ltx_scene_present": any(s.get("id") == LTX_SCENE for s in scenes) if isinstance(scenes, list) else False,
    }
    green = all(stages.values())

    report = {
        "milestone": "M3.2f",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "api": API,
        "projectId": PID,
        "projectName": project.get("name"),
        "sceneId": LTX_SCENE,
        "assetIds": {"imageA": IMAGE_A, "dialogue": DIALOGUE},
        "stages": stages,
        "probes": probes,
        "lipsyncEvidence": "artifacts/m32f/hitchhiker-production-lifecycle/06-lipsync/lipsync-still-face-cert.json",
        "exportDir": str(export_dir) if export_ok else None,
        "exportFileCount": len(export_assets),
        "stuckJobs": stuck,
        "lipsyncJobCount": len(lipsync_jobs),
        "sceneCount": len(scenes) if isinstance(scenes, list) else 0,
        "assetCount": len(assets) if isinstance(assets, list) else 0,
        "verdict": "GO" if green else "NO-GO",
        "status": "GREEN" if green else "NOT_GREEN",
    }

    (ROOT / "media-probes" / "lifecycle-probes.json").write_text(json.dumps(probes, indent=2), encoding="utf-8")
    (ROOT / "lineage" / "asset-inventory.json").write_text(
        json.dumps(
            {
                "projectId": PID,
                "scenes": [{"id": s.get("id"), "index": s.get("index"), "name": s.get("name")} for s in (scenes or [])],
                "assets": [
                    {
                        "id": a.get("id"),
                        "name": a.get("name"),
                        "kind": a.get("kind") or a.get("type"),
                        "path": a.get("path") or a.get("localPath"),
                        "parentId": a.get("parentId") or a.get("parent_asset_id"),
                        "taxonomy": a.get("taxonomy") or a.get("tags"),
                    }
                    for a in (assets or [])
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "stages": stages}, indent=2))


if __name__ == "__main__":
    main()
