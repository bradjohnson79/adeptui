"""Generate ACE-Step music + MMAudio SFX for Hitchhiker Test 2 and place on Editor."""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "d1683511-1cc7-4d3d-8cb7-00f48cc36aa9"
SCENE = "e277e621-189d-471e-b435-f01620f03d0d"
OUT_M = Path("artifacts/m32g/hitchhiker-test-2/09-music")
OUT_S = Path("artifacts/m32g/hitchhiker-test-2/10-sfx")
OUT_E = Path("artifacts/m32g/hitchhiker-test-2/11-editor")
for p in (OUT_M, OUT_S, OUT_E):
    p.mkdir(parents=True, exist_ok=True)


def call(method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_job(job_id: str, timeout: int = 900):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = call("GET", f"{API}/api/jobs/{job_id}")
        if job.get("status") in {"done", "failed", "cancelled"}:
            return job
        time.sleep(3)
    raise TimeoutError(job_id)


def generate_kind(kind: str, prompt: str, out_dir: Path) -> dict:
    # Prefer generation-tools, fall back to m29 audio generate.
    try:
        result = call(
            "POST",
            f"{API}/api/projects/{PID}/generation-tools/run",
            {
                "toolId": f"audio.{kind}.generate",
                "prompt": prompt,
                "projectId": PID,
                "sceneId": SCENE,
            },
        )
        out_dir.joinpath(f"{kind}-gen-tools.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if result.get("jobId") or result.get("id"):
            job_id = result.get("jobId") or result.get("id")
            job = wait_job(job_id)
            out_dir.joinpath(f"{kind}-job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
            return {"via": "generation-tools", "result": result, "job": job}
    except Exception as exc:  # noqa: BLE001
        out_dir.joinpath(f"{kind}-gen-tools-error.txt").write_text(str(exc), encoding="utf-8")

    result = call(
        "POST",
        f"{API}/api/codirector/m29/audio/generate",
        {
            "projectId": PID,
            "sceneId": SCENE,
            "kind": kind,
            "prompt": prompt,
            "durationSec": 4.0 if kind == "sfx" else 8.0,
        },
    )
    out_dir.joinpath(f"{kind}-m29.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return {"via": "m29", "result": result}


def place_on_editor(asset_id: str, track: str, start: float, length: float, label: str):
    editor = call("GET", f"{API}/api/projects/{PID}/editor")
    data = editor.get("data") or editor
    tracks = data.setdefault("tracks", {})
    clips = list(tracks.get(track) or [])
    clips.append(
        {
            "id": f"{track}-{asset_id[:8]}",
            "asset_id": asset_id,
            "start": start,
            "length": length,
            "trim_start": 0,
            "label": label,
            "gain": 0.35 if track == "music" else 0.55,
        }
    )
    tracks[track] = clips
    data["tracks"] = tracks
    saved = call("PUT", f"{API}/api/projects/{PID}/editor", data)
    OUT_E.joinpath(f"editor-after-{track}.json").write_text(json.dumps(saved, indent=2), encoding="utf-8")
    return saved


def extract_asset_id(payload: dict) -> str | None:
    for key in ("assetId", "asset_id", "id"):
        if payload.get(key) and key != "id":
            return str(payload[key])
    result = payload.get("result") or {}
    for key in ("assetId", "asset_id", "id"):
        if result.get(key):
            return str(result[key])
    job = payload.get("job") or {}
    meta = job.get("params_json")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if isinstance(meta, dict) and meta.get("asset_id"):
        return str(meta["asset_id"])
    # Scan project assets for newest audio
    project = call("GET", f"{API}/api/projects/{PID}")
    audios = [a for a in (project.get("assets") or []) if (a.get("kind") or "") in {"audio", "music", "sfx"}]
    if audios:
        return audios[-1].get("id")
    return None


def main() -> None:
    music = generate_kind(
        "music",
        "Sparse cinematic roadside underscore, warm dusk tones, gentle pulse, no vocals",
        OUT_M,
    )
    sfx = generate_kind(
        "sfx",
        "Distant vehicle passing on a rural highway, short whoosh, outdoor air",
        OUT_S,
    )
    music_id = extract_asset_id(music)
    sfx_id = extract_asset_id(sfx)
    summary = {"musicAssetId": music_id, "sfxAssetId": sfx_id, "music": music, "sfx": sfx}
    if music_id:
        place_on_editor(music_id, "music", 0.0, 8.0, "Test2 music")
    if sfx_id:
        place_on_editor(sfx_id, "sfx", 1.2, 2.5, "Test2 passing vehicle")
    OUT_E.joinpath("audio-placement-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"musicAssetId": music_id, "sfxAssetId": sfx_id}, indent=2))


if __name__ == "__main__":
    main()
