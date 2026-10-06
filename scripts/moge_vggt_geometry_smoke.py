"""MoGe-2 / VGGT geometry smoke on the SenseNova corridor.

Direct reconstruct → render. Outside the full Spatial Map UI.
Does not promote an engine. Does not build Viewport.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

API = "http://127.0.0.1:8758"
PROJECT = "0ffe56e2-0d58-4926-91bf-0f947898d02e"
SOURCE = "1211dd83-e3f6-4d17-bf2b-669ec5961418"
OUT = Path("docs/release-gate/spatial-map/evidence/geometry_bakeoff")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=120.0)
    health = client.get(f"{API}/api/healthz")
    print("healthz", health.status_code)
    agree = client.get(f"{API}/api/setup/essential-agreement")
    print("agreement", agree.status_code, agree.json().get("accepted"), agree.json().get("currentVersion"))
    if not agree.json().get("accepted"):
        accepted = client.post(
            f"{API}/api/setup/essential-agreement/accept",
            json={"version": agree.json().get("currentVersion"), "documentAvailableConfirmed": True},
        )
        print("accept", accepted.status_code)
    asset = client.get(f"{API}/api/assets/{SOURCE}")
    payload = asset.json() if asset.is_success else {}
    source_path = payload.get("path") or payload.get("filePath") or payload.get("localPath")
    if not source_path:
        print("source asset path missing", asset.status_code, str(payload)[:300])
        return 2
    moge = client.post(f"{API}/api/setup/geometry/moge2/install-source", json={"downloadWeights": False})
    print("moge install", moge.status_code, moge.json().get("ok"), moge.json().get("message"))
    vggt = client.post(f"{API}/api/setup/geometry/vggt/install-source", json={"downloadWeights": False})
    print("vggt install", vggt.status_code, vggt.json().get("ok"), vggt.json().get("message"))
    bake = client.post(
        f"{API}/api/setup/geometry/bakeoff",
        json={"sourcePath": source_path, "outputDir": str(OUT.resolve())},
        timeout=700.0,
    )
    print("bakeoff", bake.status_code)
    if bake.is_success:
        (OUT / "smoke_http.json").write_text(json.dumps(bake.json(), indent=2), encoding="utf-8")
    else:
        (OUT / "smoke_http.json").write_text(bake.text[:4000], encoding="utf-8")
    return 0 if bake.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
