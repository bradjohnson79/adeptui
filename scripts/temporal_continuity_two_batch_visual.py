"""One named project: I2V two-batch corridor walk+turn. Inspect the cut."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8758"
COMFY = "http://127.0.0.1:8188"
PROJECT_ID = "42ff15c3-5c39-4a7c-a430-e58e3719b6da"
SCENE_ID = "2e3a2cfc-0094-4f7c-887a-5befa08db347"
START_CLIP = Path(
    r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\output\video\Annie-Korri_00002_.mp4"
)
OUT = ROOT / "docs" / "release-gate" / "codirector-temporal-continuity" / "artifacts"
PROMPT_B1 = (
    "Cinematic two-shot. Anadriya and Korri walk a long dim corridor. "
    "Camera dollies with them. Korri begins turning toward Anadriya. "
    "The turn is unfinished at the end of the shot. Preserve identity and screen geography."
)
PROMPT_B2 = (
    "Continue the same corridor walk without resetting. "
    "Finish Korri's turn toward Anadriya. Keep walking, camera dolly, lighting, and sides of frame."
)


def _req(method: str, path: str, data: dict | None = None, timeout: int = 60) -> dict:
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


def _upload(path: Path, tag: str) -> dict:
    boundary = "----adeptBoundary"
    payload = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="tag"\r\n\r\n{tag}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="kind"\r\n\r\nimage\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}/api/projects/{PROJECT_ID}/assets",
        data=payload,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def _ffmpeg(*args: str) -> None:
    proc = subprocess.run(["ffmpeg", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg failed")[:500])


def _wait_comfy_http() -> None:
    for _ in range(40):
        try:
            urllib.request.urlopen(f"{COMFY}/system_stats", timeout=5)
            return
        except Exception:
            time.sleep(3)
    raise RuntimeError("COMFY_HTTP_UNREADY")


def _wait_vram(min_gb: float = 10.0, timeout_sec: int = 45 * 60) -> float:
    sys.path.insert(0, str(ROOT / "studio-api"))
    from app.codirector.video_intelligence.gpu_lease import query_free_vram_gb

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        free = query_free_vram_gb()
        print(f"WAIT_VRAM free={free}", flush=True)
        if free is not None and free >= min_gb:
            return float(free)
        time.sleep(20)
    raise RuntimeError(f"VRAM_WINDOW_TIMEOUT free={query_free_vram_gb()}")


def _master() -> dict:
    return _req("GET", f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/master")


def _asset_path(asset_id: str) -> Path | None:
    dest = ROOT / "data" / "assets" / PROJECT_ID
    if not dest.is_dir():
        return None
    for path in dest.iterdir():
        if path.stem == asset_id:
            return path
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not START_CLIP.is_file():
        print("START_CLIP_MISSING", START_CLIP)
        return 2
    _wait_comfy_http()
    print("COMFY_HTTP_OK", flush=True)
    _wait_vram(10.0)

    start_png = OUT / "batch1-start.png"
    _ffmpeg("-y", "-i", str(START_CLIP), "-vframes", "1", str(start_png))
    uploaded = _upload(start_png, "corridor-start")
    start_id = uploaded.get("id")
    if not start_id:
        print("UPLOAD_FAILED", uploaded)
        return 2
    print("START_ASSET", start_id, flush=True)

    workspace = _master()
    master = workspace.get("master") or {}
    batches = list(master.get("batchBlocks") or [])
    if not batches:
        added = _req(
            "POST",
            f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/batches",
            {"label": "Batch 1 corridor walk", "plannedDuration": 5.0, "generatorId": "ltx-2.5-distilled"},
        )
        batches = list((added.get("master") or {}).get("batchBlocks") or [])
    if len(batches) < 2:
        _req(
            "POST",
            f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/batches",
            {"label": "Batch 2 finish the turn", "plannedDuration": 5.0, "generatorId": "ltx-2.5-distilled"},
        )
        batches = list((_master().get("master") or {}).get("batchBlocks") or [])
    batches = sorted(batches, key=lambda b: b.get("order", 0))
    b1 = batches[0]["id"]
    b2 = batches[1]["id"]

    _req(
        "PATCH",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/batches/{b1}",
        {
            "label": "Batch 1 corridor walk",
            "generatorId": "ltx-2.5-distilled",
            "plannedDuration": 5.0,
            "promptSegments": [{"start": 0.0, "length": 5.0, "text": PROMPT_B1}],
            "sourceAnchors": [{"kind": "image", "assetId": start_id, "label": "start"}],
        },
    )
    _req(
        "PATCH",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/batches/{b2}",
        {
            "label": "Batch 2 finish the turn",
            "generatorId": "ltx-2.5-distilled",
            "plannedDuration": 5.0,
            "promptSegments": [{"start": 0.0, "length": 5.0, "text": PROMPT_B2}],
        },
    )
    policy = _req(
        "POST",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/codirector-continuity-policy",
        {"enabled": True, "reviewCadence": "every_batch", "protection": "standard"},
    )
    print("POLICY", policy.get("coDirectorContinuityPolicy"), flush=True)

    gen1 = _req(
        "POST",
        f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/batches/{b1}/generate",
        {"draftMode": True},
        timeout=120,
    )
    print("GEN1", {k: gen1.get(k) for k in ("ok", "error", "submitted", "jobId", "queueJobId")}, flush=True)
    if not gen1.get("ok"):
        (OUT / "two-batch-evidence.json").write_text(json.dumps({"gen1": gen1}, indent=2), encoding="utf-8")
        return 2

    def _live_review_and_persist() -> dict | None:
        sys.path.insert(0, str(ROOT / "studio-api"))
        os.environ["ADEPT_TEMPORAL_PERCEPTION_MODE"] = "live"
        os.environ.setdefault(
            "ADEPT_VIDEO_INTELLIGENCE_PYTHON",
            str(ROOT / "data" / "venvs" / "videochat3-worker" / "Scripts" / "python.exe"),
        )
        from app.codirector.video_intelligence.service import review_completed_batch
        from app.director_timeline_w46.contracts import SceneTimelineMaster
        from app.db import SessionLocal

        db = SessionLocal()
        try:
            workspace = _master()
            master = SceneTimelineMaster.model_validate(workspace.get("master") or {})
            source = next(b for b in master.batchBlocks if b.id == b1)
            packet = review_completed_batch(
                db, PROJECT_ID, SCENE_ID, master, source, target_batch_id=b2
            )
            _req(
                "PUT",
                f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/master",
                {"master": master.model_dump()},
            )
            return packet.model_dump(by_alias=True) if packet is not None else None
        finally:
            db.close()

    deadline = time.time() + 40 * 60
    packet = None
    b1_asset = None
    b2_asset = None
    b2_submitted = False
    live_review_done = False
    while time.time() < deadline:
        row = _master().get("master") or {}
        by_id = {b["id"]: b for b in row.get("batchBlocks") or []}
        s1 = (by_id.get(b1) or {}).get("status")
        s2 = (by_id.get(b2) or {}).get("status")
        packets = list(row.get("temporalPackets") or [])
        if packets:
            packet = packets[-1]
        clip1 = (by_id.get(b1) or {}).get("approvedClip") or {}
        clip2 = (by_id.get(b2) or {}).get("approvedClip") or {}
        b1_asset = clip1.get("assetId") or b1_asset
        b2_asset = clip2.get("assetId") or b2_asset
        print(f"POLL b1={s1} b2={s2} packet={bool(packet)} b1asset={b1_asset} b2asset={b2_asset}", flush=True)
        if b1_asset and not live_review_done:
            try:
                packet = _live_review_and_persist() or packet
                live_review_done = True
                print("LIVE_REVIEW", (packet or {}).get("availability"), flush=True)
            except Exception as exc:
                print("LIVE_REVIEW_FAIL", str(exc)[:400], flush=True)
                live_review_done = True
        if packet and not b2_submitted and s1 in ("Approved", "CandidateReady", "Ready"):
            try:
                gen2 = _req(
                    "POST",
                    f"/api/director-timeline/projects/{PROJECT_ID}/scenes/{SCENE_ID}/batches/{b2}/generate",
                    {"draftMode": True},
                    timeout=120,
                )
                print("GEN2", gen2.get("ok"), gen2.get("error"), gen2.get("reason"), flush=True)
                b2_submitted = bool(gen2.get("ok"))
            except urllib.error.HTTPError as exc:
                print("GEN2_HTTP", exc.code, exc.read()[:300], flush=True)
        if b1_asset and b2_asset and packet:
            break
        time.sleep(15)
    else:
        print("TWO_BATCH_TIMEOUT", flush=True)

    evidence = {
        "projectId": PROJECT_ID,
        "sceneId": SCENE_ID,
        "startAssetId": start_id,
        "batch1Id": b1,
        "batch2Id": b2,
        "batch1AssetId": b1_asset,
        "batch2AssetId": b2_asset,
        "packet": packet,
        "gen1": {k: gen1.get(k) for k in ("ok", "error", "jobId", "queueJobId", "request")},
    }
    if packet:
        evidence["packetAvailability"] = packet.get("availability")
        evidence["unfinishedActions"] = (packet.get("observation") or {}).get("unfinishedActions") or packet.get(
            "unfinishedActions"
        )
        evidence["directives"] = (packet.get("continuation") or {}).get("nextBatchDirectives")
    if b1_asset and b2_asset:
        p1 = _asset_path(b1_asset)
        p2 = _asset_path(b2_asset)
        if p1 and p2:
            last = OUT / "batch1-last-1p5s.mp4"
            first = OUT / "batch2-first-1p5s.mp4"
            last_png = OUT / "batch1-last-frame.png"
            first_png = OUT / "batch2-first-frame.png"
            _ffmpeg("-y", "-sseof", "-1.5", "-i", str(p1), "-t", "1.5", str(last))
            _ffmpeg("-y", "-i", str(p2), "-t", "1.5", str(first))
            _ffmpeg("-y", "-sseof", "-0.04", "-i", str(p1), "-vframes", "1", str(last_png))
            _ffmpeg("-y", "-i", str(p2), "-vframes", "1", str(first_png))
            evidence["batch1Path"] = str(p1)
            evidence["batch2Path"] = str(p2)
            evidence["inspectClips"] = [str(last), str(first), str(last_png), str(first_png)]
    (OUT / "two-batch-evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("EVIDENCE", OUT / "two-batch-evidence.json", flush=True)
    if not (b1_asset and b2_asset and packet):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
