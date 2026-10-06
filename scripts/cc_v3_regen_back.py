import json
import time
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8758"
PID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1"
CID = "cf4437c7-fd89-4baa-90f3-8098d19eac31"
OUT = Path("docs/release-gate/character-creator/evidence/cc_v3_angles/back.png")


def get(path):
    with urllib.request.urlopen(API + path, timeout=60) as resp:
        return json.loads(resp.read().decode())


def post(path):
    req = urllib.request.Request(
        API + path, data=b"{}", headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


started = time.time()
post(f"/api/projects/{PID}/characters/{CID}/multiview/back/regenerate")
slot = {}
while time.time() - started < 420:
    time.sleep(8)
    st = get(f"/api/projects/{PID}/characters/{CID}/cc-v2")
    slot = ((st.get("multiView") or {}).get("angles") or {}).get("back") or {}
    print(round(time.time() - started, 1), slot.get("status"), slot.get("assetId"), slot.get("error"))
    if slot.get("assetId") and slot.get("status") not in {"generating", "queued", "running"}:
        break
    if slot.get("status") == "failed":
        break

aid = slot.get("assetId")
if aid:
    with urllib.request.urlopen(API + f"/api/assets/{aid}/file", timeout=60) as resp:
        OUT.write_bytes(resp.read())
    print("saved", OUT, OUT.stat().st_size)
else:
    raise SystemExit("back regenerate produced no asset")
