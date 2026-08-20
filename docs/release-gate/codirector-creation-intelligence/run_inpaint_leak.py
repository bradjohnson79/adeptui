"""Measure zimage.inpaint leak on the live Schnick still."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "studio-api"))

API = "http://127.0.0.1:8758"
PROJECT = "2347bf46-3762-4763-86c5-4a6032522278"
EVIDENCE = Path(__file__).resolve().parent / "evidence"
SRC = EVIDENCE / "schnick-still.png"
MASK = EVIDENCE / "edit-mask.png"
IDS = EVIDENCE / "_live_ids.json"


def main() -> int:
    ids = json.loads(IDS.read_text(encoding="utf-8"))
    with Image.open(SRC) as im:
        mask = Image.new("L", im.size, 0)
        draw = ImageDraw.Draw(mask)
        w, h = im.size
        draw.ellipse((int(w * 0.45), int(h * 0.40), int(w * 0.92), int(h * 0.88)), fill=255)
        mask.save(MASK)
    print("mask", MASK, MASK.stat().st_size)

    boundary = uuid.uuid4().hex
    file_bytes = MASK.read_bytes()
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="edit-mask.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode() + file_bytes + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="tag"\r\n\r\n'
        "inpaint_mask"
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="kind"\r\n\r\n'
        "image"
        f"\r\n--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        f"{API}/api/projects/{PROJECT}/assets",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=90) as res:
        uploaded = json.loads(res.read().decode())
    mask_id = str(uploaded.get("id") or "")
    print("mask upload", mask_id)
    if not mask_id:
        return 1

    payload = json.dumps(
        {
            "operation": "add",
            "prompt": "add a red coffee mug on the counter",
            "maskAssetId": mask_id,
            "sourceAssetId": ids["schnickAssetId"],
            "stage": "preview",
            "local_family": "zimage",
            "local_enabled": True,
            "api_enabled": False,
        }
    ).encode()
    req = urllib.request.Request(
        f"{API}/api/scene-creator/projects/{PROJECT}/shots/{ids['schnickShotId']}/region-edit",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            started = json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        print("edit HTTP", exc.code, exc.read().decode()[:2000])
        return 1

    shot = started.get("shot") or started
    job_ids = []
    for cand in shot.get("candidates") or []:
        print("cand", cand.get("kind"), cand.get("job_id") or cand.get("jobId"), cand.get("status"))
        if cand.get("kind") == "region_edit" or cand.get("edit_operation"):
            jid = cand.get("job_id") or cand.get("jobId")
            status = str(cand.get("status") or "").lower()
            if jid and status not in {"failed", "error", "cancelled", "complete", "done"}:
                job_ids.append(str(jid))
    if not job_ids:
        for cand in reversed(shot.get("candidates") or []):
            if cand.get("kind") == "region_edit" or cand.get("edit_operation"):
                jid = cand.get("job_id") or cand.get("jobId")
                if jid:
                    job_ids.append(str(jid))
                    break
    for jid in job_ids:
        for i in range(48):
            with urllib.request.urlopen(f"{API}/api/jobs/{jid}", timeout=20) as res:
                job = json.loads(res.read().decode())
            print("job", i, job.get("status"), job.get("progress"), str(job.get("message") or "")[:140])
            if str(job.get("status") or "").lower() in {"done", "failed", "error", "cancelled"}:
                break
            time.sleep(5)

    edit_asset = ""
    for _ in range(24):
        with urllib.request.urlopen(
            f"{API}/api/scene-creator/projects/{PROJECT}/shots/{ids['schnickShotId']}",
            timeout=20,
        ) as res:
            shot = json.loads(res.read().decode())["shot"]
        for cand in shot.get("candidates") or []:
            if cand.get("kind") == "region_edit" or cand.get("edit_operation"):
                aid = str(cand.get("asset_id") or cand.get("assetId") or "")
                status = str(cand.get("status") or "").lower()
                print("edit cand", cand.get("kind"), status, aid)
                if aid and status in {"done", "ready", "approved", "complete"}:
                    edit_asset = aid
        if edit_asset:
            break
        time.sleep(3)

    print("edit_asset", edit_asset)
    if not edit_asset:
        return 1
    dest = EVIDENCE / "edit-inpaint.png"
    urllib.request.urlretrieve(f"{API}/api/assets/{edit_asset}/file", dest)
    print("saved", dest, dest.stat().st_size)
    from app.codirector.perception.inpaint_leak import LEAK_THRESHOLD, unmasked_mean_delta

    delta = unmasked_mean_delta(dest, SRC, MASK)
    print("leak", delta, "threshold", LEAK_THRESHOLD, "ok", float(delta) <= 2.0)
    ids["editAssetId"] = edit_asset
    ids["maskAssetId"] = mask_id
    ids["leak"] = delta
    IDS.write_text(json.dumps(ids, indent=2), encoding="utf-8")
    return 0 if float(delta) <= 2.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
