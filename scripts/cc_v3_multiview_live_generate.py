"""Live Character Angles generate for Mira Vale on Adept Stability Cert."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1"
CID = "cf4437c7-fd89-4baa-90f3-8098d19eac31"
OUT = Path("docs/release-gate/character-creator/evidence/cc_v3_multiview_live_generate.json")
IMG_DIR = Path("docs/release-gate/character-creator/evidence/cc_v3_angles")


def get(path: str):
    with urllib.request.urlopen(f"{API}{path}", timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post(path: str, body: dict | None = None):
    raw = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"raw": payload}
        return exc.code, parsed


def gpu_snapshot() -> dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        devices = data.get("devices") or []
        first = devices[0] if devices else {}
        return {
            "name": first.get("name"),
            "type": first.get("type"),
            "vram_total": first.get("vram_total"),
            "vram_free": first.get("vram_free"),
            "torch_vram_used": first.get("torch_vram_used") or first.get("vram_used"),
        }
    except Exception as exc:
        return {"error": str(exc)}


def download_asset(asset_id: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{API}/api/assets/{asset_id}/file"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            dest.write_bytes(resp.read())
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        return False


def main() -> int:
    started = time.time()
    before = gpu_snapshot()
    code, payload = post(f"/api/projects/{PID}/characters/{CID}/multiview/generate")
    after_submit = gpu_snapshot()
    report = {
        "submitStatus": code,
        "submit": {
            "phase": payload.get("phase") if isinstance(payload, dict) else None,
            "activeJobView": payload.get("activeJobView") if isinstance(payload, dict) else None,
            "multiView": (payload.get("multiView") if isinstance(payload, dict) else None),
            "error": payload if code >= 400 else None,
        },
        "gpuBefore": before,
        "gpuAfterSubmit": after_submit,
        "polls": [],
        "angles": {},
        "durationSec": None,
        "verdict": "RUNNING",
    }
    if code >= 400:
        report["verdict"] = f"NO-GO — generate returned {code}"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    deadline = time.time() + 900
    final = payload
    while time.time() < deadline:
        time.sleep(8)
        final = get(f"/api/projects/{PID}/characters/{CID}/cc-v2")
        mv = final.get("multiView") or {}
        angles = mv.get("angles") or {}
        snap = {
            "t": round(time.time() - started, 1),
            "status": mv.get("status"),
            "gpu": gpu_snapshot(),
            "angles": {
                name: {
                    "status": (angles.get(name) or {}).get("status"),
                    "assetId": (angles.get(name) or {}).get("assetId"),
                    "promptId": (angles.get(name) or {}).get("promptId"),
                    "error": (angles.get(name) or {}).get("error"),
                }
                for name in ("side", "three_quarter", "back")
            },
        }
        report["polls"].append(snap)
        statuses = [str((angles.get(name) or {}).get("status") or "") for name in ("side", "three_quarter", "back")]
        if all(s in {"ready", "approved", "review"} or (angles.get(name) or {}).get("assetId") for name, s in zip(("side", "three_quarter", "back"), statuses)):
            if not any(s in {"generating", "queued", "running", "starting"} for s in statuses) and mv.get("status") not in {"generating", "queued"}:
                break
        if any(s == "failed" for s in statuses) and not any(s in {"generating", "queued", "running"} for s in statuses):
            break

    report["durationSec"] = round(time.time() - started, 1)
    report["gpuAfter"] = gpu_snapshot()
    mv = (final or {}).get("multiView") or {}
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    front_id = (((final or {}).get("views") or {}).get("front") or {}).get("assetId")
    if front_id:
        download_asset(str(front_id), IMG_DIR / "front.png")
    for name in ("side", "three_quarter", "back"):
        slot = (mv.get("angles") or {}).get(name) or {}
        aid = slot.get("assetId")
        saved = download_asset(str(aid), IMG_DIR / f"{name}.png") if aid else False
        report["angles"][name] = {
            "status": slot.get("status"),
            "assetId": aid,
            "promptId": slot.get("promptId"),
            "jobId": slot.get("jobId"),
            "error": slot.get("error"),
            "runtime": slot.get("runtime"),
            "seed": slot.get("seed"),
            "saved": saved,
            "bytes": (IMG_DIR / f"{name}.png").stat().st_size if saved else 0,
        }
    ready = all(row.get("saved") for row in report["angles"].values())
    report["verdict"] = "GO — three live angle files saved" if ready else "NO-GO — missing live angle files"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("submitStatus", "durationSec", "gpuAfter", "angles", "verdict")}, indent=2))
    return 0 if ready else 3


if __name__ == "__main__":
    raise SystemExit(main())
