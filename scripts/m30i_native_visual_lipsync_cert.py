#!/usr/bin/env python3
"""M3.0i native product-route: visual continuity + LatentSync lipsync + export (local Comfy, no fal)."""
from __future__ import annotations
import hashlib, json, mimetypes, os, sys, time, urllib.error, urllib.request, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "m30i" / "native-production" / "product-route"
CONTINUITY_SPEC = ROOT / "artifacts" / "m30i" / "native-production" / "preflight" / "continuity-spec.json"
AUDIO_ROUTE = OUT / "audio-product-route.json"
REUSE_PROJECT = os.environ.get("M30I_REUSE_PROJECT_ID", "").strip()
M30H_PROJECT = "2f561428-7a17-4d0a-917f-6da6c0960837"
API = os.environ.get("STUDIO_API_BASE", "http://127.0.0.1:8743").rstrip("/")
POLL_SEC = 3
JOB_TIMEOUT_SEC = int(os.environ.get("M30I_JOB_TIMEOUT_SEC", str(2 * 3600)))
NEGATIVE = "crowd, second person, duplicate body, twin, text, watermark, blurry, extra faces, deformed hands"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _file_meta(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {"exists": False, "path": str(path) if path else None}
    st = path.stat()
    return {"exists": True, "path": str(path.resolve()), "bytes": st.st_size, "sha256": _sha256(path)}

def _req(method: str, path: str, body: dict | None = None, timeout: float = 300) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{API}{path}", data=data, method=method, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {e.code}: {detail[:3000]}") from e

def _wait_job(job_id: str, label: str = "") -> dict[str, Any]:
    started = time.time()
    last_msg = ""
    while time.time() - started < JOB_TIMEOUT_SEC:
        job = _req("GET", f"/api/jobs/{job_id}", timeout=60)
        status = job.get("status")
        msg = job.get("message") or ""
        if msg != last_msg:
            print(f"  [{label or job_id}] {status}: {msg[:120]}")
            last_msg = msg
        if status in ("done", "failed", "cancelled"):
            return job
        time.sleep(POLL_SEC)
    raise TimeoutError(f"job {job_id} ({label}) timed out after {JOB_TIMEOUT_SEC}s")


COMFY_INSTALL_INPUT = Path(r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\input")

def _mirror_comfy_install_input(file_path: Path, subfolder: str = "studio") -> Path:
    dest_dir = COMFY_INSTALL_INPUT / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file_path.name
    if not dest.is_file() or dest.stat().st_size != file_path.stat().st_size:
        dest.write_bytes(file_path.read_bytes())
    return dest

def _upload_asset(project_id: str, file_path: Path, *, tag: str, kind: str) -> dict[str, Any]:
    boundary = uuid.uuid4().hex
    filename = file_path.name
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()
    parts: list[bytes] = []
    for name, value in (("tag", tag), ("kind", kind)):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    parts.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n").encode() + file_bytes + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(f"{API}/api/projects/{project_id}/assets", data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _library_asset(project_id: str, asset_id: str) -> dict[str, Any] | None:
    assets = _req("GET", f"/api/projects/{project_id}/library")
    if isinstance(assets, dict):
        assets = assets.get("assets") or assets.get("items") or []
    return next((a for a in assets if a.get("id") == asset_id), None)

def _job_output_asset_id(job: dict[str, Any]) -> str | None:
    params = job.get("params_json")
    if isinstance(params, str):
        try:
            params = json.loads(params or "{}")
        except json.JSONDecodeError:
            params = {}
    if isinstance(params, dict):
        return params.get("output_asset_id") or params.get("asset_id")
    return None

def _scene_output_path(project_id: str, scene_id: str) -> Path | None:
    project = _req("GET", f"/api/projects/{project_id}")
    scene = next((s for s in (project.get("scenes") or []) if s.get("id") == scene_id), None)
    if not scene:
        return None
    p = scene.get("output_path")
    return Path(p) if p else None

def _load_spec() -> dict[str, Any]:
    if CONTINUITY_SPEC.is_file():
        return json.loads(CONTINUITY_SPEC.read_text(encoding="utf-8"))
    return {}

def _resolve_project() -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {"reuseAttempted": []}
    for pid in [REUSE_PROJECT, M30H_PROJECT]:
        if not pid:
            continue
        meta["reuseAttempted"].append(pid)
        try:
            proj = _req("GET", f"/api/projects/{pid}")
            if proj.get("id"):
                meta["reused"] = pid
                return pid, meta
        except Exception as exc:
            meta.setdefault("reuseErrors", []).append({pid: str(exc)[:500]})
    spec = _load_spec()
    proj = _req("POST", "/api/projects", {"name": spec.get("projectName") or "M3.0i Native Visual Lipsync Product Route", "global_prompt": spec.get("shotA") or "Cinematic hitchhiker continuity scene", "negative_prompt": NEGATIVE, "vram_gb": 24, "width": 1280, "height": 720, "fps": 24, "seed": 301027})
    meta["created"] = True
    return proj["id"], meta

def _generate_image(project_id: str, case_id: str, prompt: str, tag: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": case_id, "kind": "image", "startedAt": _now(), "prompt": prompt}
    try:
        job = _req("POST", f"/api/projects/{project_id}/imagegen", {"prompt": prompt, "negative": NEGATIVE, "model": "auto", "width": 1024, "height": 1024, "providerPreference": "local", "paidFallbackApproved": False, "tag": tag, "seed": 301027})
        entry["jobId"] = job.get("id")
        done = _wait_job(job["id"], case_id)
        entry["jobStatus"] = done.get("status")
        entry["jobMessage"] = done.get("message")
        if done.get("status") != "done":
            entry.update(ok=False, status="NOT_GREEN", reason=done.get("message") or "imagegen job failed")
            return entry
        asset_id = _job_output_asset_id(done)
        entry["assetId"] = asset_id
        asset = _library_asset(project_id, asset_id) if asset_id else None
        path = Path(asset["path"]) if asset and asset.get("path") else None
        params = json.loads(done.get("params_json") or "{}")
        entry["engine"] = params.get("model") or params.get("provider") or "comfyui-local"
        entry["provenance"] = {"source": "studio-queue-imagegen", "jobId": done.get("id"), "params": {k: params.get(k) for k in ("model", "provider", "providerPreference", "tag")}}
        entry.update(_file_meta(path))
        entry["ok"] = bool(path and path.is_file() and path.stat().st_size > 5000)
        entry["status"] = "GREEN" if entry["ok"] else "NOT_GREEN"
        if not entry["ok"]:
            entry["reason"] = "missing or tiny output image"
    except Exception as exc:
        entry.update(ok=False, status="NOT_GREEN", reason=str(exc)[:2000])
    entry["finishedAt"] = _now()
    return entry

def _render_scene(project_id: str, case_id: str, *, engine: str, scene_name: str, prompt: str, start_asset_id: str, still_model: str, duration_sec: float = 4.0) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": case_id, "kind": "video", "engine": engine, "startedAt": _now(), "startAssetId": start_asset_id}
    try:
        scene = _req("POST", f"/api/projects/{project_id}/scenes", {"name": scene_name, "prompt": prompt, "duration_sec": duration_sec, "engine": engine, "start_asset_id": start_asset_id})
        scene_id = scene["id"]
        entry["sceneId"] = scene_id
        _req("POST", f"/api/projects/{project_id}/promote", {"asset_id": start_asset_id, "target": "scene_start", "scene_id": scene_id})
        _req("PATCH", f"/api/projects/{project_id}/scenes/{scene_id}", {"engine": engine, "prompt": prompt, "duration_sec": duration_sec, "start_asset_id": start_asset_id})
        render = _req("POST", f"/api/projects/{project_id}/render", {"kind": "scene", "scene_id": scene_id, "providerPreference": "local", "paidFallbackApproved": False, "startFrameModel": still_model, "generate_audio": False})
        entry["jobId"] = render.get("id")
        done = _wait_job(render["id"], case_id)
        entry["jobStatus"] = done.get("status")
        entry["jobMessage"] = done.get("message")
        if done.get("status") != "done":
            entry.update(ok=False, status="NOT_GREEN", reason=done.get("message") or f"{engine} render failed")
            return entry
        out_path = _scene_output_path(project_id, scene_id)
        rp = json.loads(done.get("params_json") or "{}")
        entry["provenance"] = {"source": "studio-queue-render_scene", "jobId": done.get("id"), "sceneId": scene_id, "videoProvider": "comfyui", "videoModel": "ltx-2.3" if engine == "ltx" else "wan", "localFirstProvenance": rp.get("localFirstProvenance"), "ltxStartFrameBinding": rp.get("ltxStartFrameBinding")}
        entry.update(_file_meta(out_path))
        entry["ok"] = bool(out_path and out_path.is_file() and out_path.stat().st_size > 10000)
        entry["status"] = "GREEN" if entry["ok"] else "NOT_GREEN"
        if not entry["ok"]:
            entry["reason"] = "scene output_path missing or too small"
    except Exception as exc:
        entry.update(ok=False, status="NOT_GREEN", reason=str(exc)[:2000])
    entry["finishedAt"] = _now()
    return entry

def _dialogue_asset(project_id: str, line: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": "AUDIO-DIALOGUE-LIPSYNC", "startedAt": _now()}
    try:
        if AUDIO_ROUTE.is_file():
            ar = json.loads(AUDIO_ROUTE.read_text(encoding="utf-8"))
            for c in ar.get("cases") or []:
                if c.get("kind") == "dialogue" and c.get("ok"):
                    p = Path(str((c.get("result") or {}).get("assetPath") or ""))
                    if p.is_file():
                        up = _upload_asset(project_id, p, tag="kokoro_dialogue", kind="audio")
                        entry.update(source="reuse-audio-product-route", assetId=up.get("id"))
                        entry.update(_file_meta(p))
                        entry.update(ok=True, status="GREEN", finishedAt=_now())
                        return entry
        result = _req("POST", "/api/codirector/m29/audio/generate", {"projectId": project_id, "kind": "dialogue", "prompt": line, "durationSec": 3, "registryId": "m2101-dialogue-001", "seed": 42}, timeout=900)
        path = Path(str(result.get("assetPath") or ""))
        asset_id = result.get("assetId")
        if path.is_file() and not asset_id:
            up = _upload_asset(project_id, path, tag="kokoro_dialogue", kind="audio")
            asset_id = up.get("id")
        entry["source"] = "api-generate"
        entry["assetId"] = asset_id
        entry["result"] = {k: result.get(k) for k in ("assetPath", "sha256", "durationSec", "registryId")}
        if asset_id:
            asset = _library_asset(project_id, asset_id)
            if asset and asset.get("path"):
                path = Path(asset["path"])
        entry.update(_file_meta(path))
        if path.is_file():
            _mirror_comfy_install_input(path)
        entry["ok"] = bool(asset_id and path.is_file())
        entry["status"] = "GREEN" if entry["ok"] else "NOT_GREEN"
        if not entry["ok"]:
            entry["reason"] = "dialogue audio not registered in project library"
    except Exception as exc:
        entry.update(ok=False, status="NOT_GREEN", reason=str(exc)[:2000])
    entry["finishedAt"] = _now()
    return entry

def _lipsync(project_id: str, scene_id: str, audio_asset_id: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": "LIPSYNC-LATENTSYNC-01", "kind": "lipsync", "engine": "LatentSync", "startedAt": _now(), "sceneId": scene_id, "audioAssetId": audio_asset_id}
    try:
        before = _scene_output_path(project_id, scene_id)
        entry["inputVideo"] = _file_meta(before)
        job = _req("POST", f"/api/projects/{project_id}/lipsync", {"scene_id": scene_id, "audio_asset_id": audio_asset_id})
        entry["jobId"] = job.get("id")
        done = _wait_job(job["id"], "lipsync")
        entry["jobStatus"] = done.get("status")
        entry["jobMessage"] = done.get("message")
        if done.get("status") != "done":
            entry.update(ok=False, status="NOT_GREEN", reason=done.get("message") or "lipsync job failed")
            return entry
        project = _req("GET", f"/api/projects/{project_id}")
        scene = next((s for s in (project.get("scenes") or []) if s.get("id") == scene_id), {})
        out_path = Path(scene.get("output_path") or "")
        lipsync_path = out_path.with_name(out_path.stem + "_lipsync.mp4") if out_path else None
        chosen = lipsync_path if lipsync_path and lipsync_path.is_file() else out_path
        entry["outputPath"] = str(chosen) if chosen else None
        entry["provenance"] = {"source": "studio-queue-lipsync", "jobId": done.get("id"), "nodePreference": "D_LatentSyncNode|LatentSyncNode", "dialogueEngine": "kokoro"}
        entry.update(_file_meta(chosen if chosen and chosen.is_file() else None))
        entry["ok"] = bool(chosen and chosen.is_file() and chosen.stat().st_size > 10000)
        entry["status"] = "GREEN" if entry["ok"] else "NOT_GREEN"
        if not entry["ok"]:
            entry["reason"] = "lipsync output not found on disk"
    except Exception as exc:
        entry.update(ok=False, status="NOT_GREEN", reason=str(exc)[:2000])
    entry["finishedAt"] = _now()
    return entry

def _export(project_id: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": "EXPORT-AV-01", "startedAt": _now()}
    try:
        job = _req("POST", f"/api/projects/{project_id}/export", {})
        entry["jobId"] = job.get("id")
        done = _wait_job(job["id"], "export")
        entry["jobStatus"] = done.get("status")
        entry["jobMessage"] = done.get("message")
        out = done.get("output_path")
        entry["outputPath"] = out
        export_path = Path(str(out)) if out else None
        playable: Path | None = None
        if export_path and export_path.is_file():
            playable = export_path
        elif export_path and export_path.is_dir():
            for ext in ("*.mp4", "*.mov", "*.mkv", "*.webm"):
                hits = sorted(export_path.rglob(ext), key=lambda p: p.stat().st_mtime, reverse=True)
                if hits:
                    playable = hits[0]
                    break
        entry.update(_file_meta(playable))
        entry["exportDir"] = str(export_path) if export_path else None
        entry["ok"] = done.get("status") == "done" and bool(playable and playable.is_file())
        entry["status"] = "GREEN" if entry["ok"] else "NOT_GREEN"
        if not entry["ok"]:
            entry["reason"] = done.get("message") or "export did not produce a file"
    except Exception as exc:
        entry.update(ok=False, status="NOT_GREEN", reason=str(exc)[:2000])
    entry["finishedAt"] = _now()
    return entry

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    spec = _load_spec()
    continuity: dict[str, Any] = {"startedAt": _now(), "api": API, "continuitySpec": str(CONTINUITY_SPEC), "executionClass": "REAL_LOCAL_EXECUTION", "paidProviderUsed": False, "falSubmissionCount": 0, "cases": []}
    lipsync_report: dict[str, Any] = {"startedAt": _now(), "api": API, "cases": []}
    export_report: dict[str, Any] = {"startedAt": _now(), "api": API}
    print("API health...")
    health = _req("GET", "/api/health")
    continuity["comfy"] = {"reachable": (health.get("comfy") or {}).get("reachable"), "status": health.get("comfy_status")}
    continuity["operatorFlags"] = {k: (health.get("operator") or {}).get(k) for k in ("imageProductionEnabled", "videoProductionEnabled", "lipsyncProductionEnabled", "audioProductionEnabled", "editingProductionEnabled", "renderProductionEnabled")}
    project_id, proj_meta = _resolve_project()
    continuity["projectId"] = project_id
    continuity["projectMeta"] = proj_meta
    lipsync_report["projectId"] = project_id
    export_report["projectId"] = project_id
    print("Project", project_id)
    char = spec.get("character") or {}
    char_bits = ", ".join(filter(None, [char.get("genderPresentation"), char.get("approximateAge"), char.get("hair"), char.get("wardrobe")]))
    env_bits = ", ".join(filter(None, [(spec.get("environment") or {}).get("road"), (spec.get("environment") or {}).get("timeOfDay"), (spec.get("environment") or {}).get("weather")]))
    id_ref = char.get("identityReference") or "same principal hitchhiker across shots"
    shot_a = spec.get("shotA") or "medium shot hitchhiker beside highway"
    shot_b = spec.get("shotB") or "wider establishing hitchhiker on highway"
    identity = f"Exactly one hitchhiker, same person across shots, {char_bits}. Environment: {env_bits}. {id_ref}"
    prompt_a = f"{shot_a}. {identity}"
    prompt_b = f"{shot_b}. {identity}"
    motion_ltx = "Same hitchhiker beside lonely highway, slow subtle motion, golden hour, single character, no dialogue, cinematic"
    motion_wan = "Same hitchhiker on rural highway, gentle camera drift, empty road, single character, cinematic, no dialogue"
    img_a = _generate_image(project_id, "VIS-CONT-IMAGE-A", prompt_a, "m30i_image_a")
    continuity["cases"].append(img_a)
    print(img_a["id"], img_a.get("status"), img_a.get("reason") or img_a.get("path"))
    img_b = _generate_image(project_id, "VIS-CONT-IMAGE-B", prompt_b, "m30i_image_b")
    continuity["cases"].append(img_b)
    print(img_b["id"], img_b.get("status"), img_b.get("reason") or img_b.get("path"))
    still_model = str((img_a.get("provenance") or {}).get("params", {}).get("model") or "auto")
    ltx_case: dict[str, Any] = {"id": "VIS-CONT-LTX-SHOT1", "status": "NOT_GREEN", "ok": False, "reason": "Image A not GREEN"}
    wan_case: dict[str, Any] = {"id": "VIS-CONT-WAN-SHOT2", "status": "NOT_GREEN", "ok": False, "reason": "Image B not GREEN"}
    if img_a.get("ok") and img_a.get("assetId"):
        ltx_case = _render_scene(project_id, "VIS-CONT-LTX-SHOT1", engine="ltx", scene_name="LTX Shot1 (Image A)", prompt=motion_ltx, start_asset_id=str(img_a["assetId"]), still_model=still_model)
    if img_b.get("ok") and img_b.get("assetId"):
        wan_case = _render_scene(project_id, "VIS-CONT-WAN-SHOT2", engine="wan", scene_name="WAN Shot2 (Image B)", prompt=motion_wan, start_asset_id=str(img_b["assetId"]), still_model=still_model)
    continuity["cases"].extend([ltx_case, wan_case])
    print(ltx_case["id"], ltx_case.get("status"), ltx_case.get("reason") or "")
    print(wan_case["id"], wan_case.get("status"), wan_case.get("reason") or "")
    continuity["allOk"] = all(c.get("ok") for c in continuity["cases"])
    continuity["status"] = "GREEN" if continuity["allOk"] else "NOT_GREEN"
    continuity["finishedAt"] = _now()
    (OUT / "visual-continuity.json").write_text(json.dumps(continuity, indent=2), encoding="utf-8")
    dialogue_line = spec.get("dialogueLine") or "Are you heading into town?"
    dialogue = _dialogue_asset(project_id, dialogue_line)
    lipsync_report["cases"].append(dialogue)
    print(dialogue["id"], dialogue.get("status"), dialogue.get("reason") or dialogue.get("assetId"))
    lipsync_case: dict[str, Any] = {"id": "LIPSYNC-LATENTSYNC-01", "status": "NOT_GREEN", "ok": False, "reason": "LTX scene or dialogue not ready"}
    ltx_scene_id = ltx_case.get("sceneId")
    if ltx_case.get("ok") and ltx_scene_id and dialogue.get("ok") and dialogue.get("assetId"):
        lipsync_case = _lipsync(project_id, str(ltx_scene_id), str(dialogue["assetId"]))
    lipsync_report["cases"].append(lipsync_case)
    print(lipsync_case["id"], lipsync_case.get("status"), lipsync_case.get("reason") or "")
    lipsync_report["allOk"] = all(c.get("ok") for c in lipsync_report["cases"])
    lipsync_report["status"] = "GREEN" if lipsync_report["allOk"] else "NOT_GREEN"
    lipsync_report["finishedAt"] = _now()
    (OUT / "lipsync-product-route.json").write_text(json.dumps(lipsync_report, indent=2), encoding="utf-8")
    export_case = _export(project_id)
    export_report["case"] = export_case
    export_report["status"] = export_case.get("status")
    export_report["finishedAt"] = _now()
    (OUT / "export.json").write_text(json.dumps(export_report, indent=2), encoding="utf-8")
    print(export_case["id"], export_case.get("status"), export_case.get("reason") or export_case.get("outputPath"))
    overall = continuity["allOk"] and lipsync_report["allOk"]
    print("OVERALL", "GREEN" if overall else "NOT_GREEN")
    print("visual-continuity", OUT / "visual-continuity.json")
    print("lipsync", OUT / "lipsync-product-route.json")
    print("export", OUT / "export.json")
    return 0 if overall else 1

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        err = {"status": "NOT_GREEN", "error": str(exc), "finishedAt": _now(), "api": API}
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "visual-continuity.json").write_text(json.dumps(err, indent=2), encoding="utf-8")
        print(f"FATAL: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc




