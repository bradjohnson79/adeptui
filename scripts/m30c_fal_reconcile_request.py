"""Reconcile an already-submitted fal request into Studio Job + Asset (no new submit)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "studio-api"))

JOB_ID = "5875e029-9693-4ca9-8bb1-f0d0169f37a2"
PROJECT_ID = "fb3398dd-df7e-455b-ab0d-400e5390eb33"
REQUEST_ID = "019fa4f6-7a76-72c1-bfe3-ed8cb5200707"
MODEL_ID = "bytedance/seedance-2.0/text-to-video"
OUT = ROOT / "artifacts" / "m30c-fal"


async def main() -> int:
    from app.config import settings
    from app.db import Asset, Job, SessionLocal, init_db
    from app.fal_client import download_url, extract_video_url
    from app.secrets_store import get_secret
    import httpx

    # Prefer bridged secret store; fall back to env (never print).
    api_key = (get_secret("fal_api_key") or os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY") or "").strip()
    if not api_key:
        print("NO_KEY")
        return 2

    headers = {"Authorization": f"Key {api_key}", "Accept": "application/json"}
    status_url = f"https://queue.fal.run/{MODEL_ID}/requests/{REQUEST_ID}/status"
    response_url = f"https://queue.fal.run/{MODEL_ID}/requests/{REQUEST_ID}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        for _ in range(180):
            st = await client.get(status_url, headers=headers)
            body = st.json() if st.status_code < 400 else {"http": st.status_code, "text": st.text[:300]}
            status = str(body.get("status") or "").upper()
            print(f"FAL_STATUS={status or st.status_code}")
            if status == "COMPLETED":
                resp = await client.get(response_url, headers=headers)
                result = resp.json()
                break
            if status in ("FAILED", "CANCELLED", "ERROR"):
                print(f"FAL_FAILED={body}")
                return 1
            await asyncio.sleep(5)
        else:
            print("FAL_TIMEOUT")
            return 1

    video_url = extract_video_url(result)
    dest = settings.data_dir / "projects" / PROJECT_ID / "assets" / f"m30c_fal_{REQUEST_ID[:8]}.mp4"
    await download_url(video_url, dest)
    size = dest.stat().st_size
    print(f"DOWNLOADED_BYTES={size}")

    init_db()
    db = SessionLocal()
    try:
        job = db.get(Job, JOB_ID)
        if not job:
            print("JOB_MISSING")
            return 1
        hist = {}
        try:
            hist = json.loads(job.history_json or "{}")
        except json.JSONDecodeError:
            hist = {}
        hist["falRequestId"] = REQUEST_ID
        hist["falModelId"] = MODEL_ID
        hist["reconciled"] = True
        hist["reconcileNote"] = "Completed via provider request lookup after API restart interrupted local worker"
        asset = Asset(
            id=f"video-{REQUEST_ID[:12]}",
            project_id=PROJECT_ID,
            filename=dest.name,
            path=str(dest),
            kind="video",
            tag="m30c-fal-unified-proof",
            meta_json=json.dumps(
                {
                    "provider": "fal",
                    "engine": "fal_seedance",
                    "request_id": REQUEST_ID,
                    "model": MODEL_ID,
                    "reconciled": True,
                    "bytes": size,
                }
            ),
        )
        db.merge(asset)
        job.status = "done"
        job.stage = "complete"
        job.progress = 1.0
        job.message = "fal Seedance reconciled from provider request_id"
        job.output_path = str(dest)
        job.history_json = json.dumps(hist)
        db.commit()
        print(f"JOB_DONE asset={asset.id}")
    finally:
        db.close()

    OUT.mkdir(parents=True, exist_ok=True)
    evidence_path = OUT / "unified_queue_proof.json"
    prior = {}
    if evidence_path.exists():
        prior = json.loads(evidence_path.read_text(encoding="utf-8"))
    prior.update(
        {
            "outcome": "SUCCESS",
            "submitted": True,
            "reconciled": True,
            "falRequestId": REQUEST_ID,
            "jobFinal": {
                "id": JOB_ID,
                "status": "done",
                "outputPath": str(dest),
                "bytes": size,
            },
            "codirectorInspect": {"note": "re-verify via GET /api/codirector/jobs/{id}"},
            "guard": "No second fal submit; reconciled existing request_id after worker interrupt",
        }
    )
    evidence_path.write_text(json.dumps(prior, indent=2) + "\n", encoding="utf-8")
    print("EVIDENCE_UPDATED")
    return 0


if __name__ == "__main__":
    # Ensure same data dir as the API that created the job.
    os.environ.setdefault("STUDIO_DATA_DIR", str(Path(os.environ.get("TEMP", "/tmp")) / "adept-m30c-fal-data"))
    raise SystemExit(asyncio.run(main()))
