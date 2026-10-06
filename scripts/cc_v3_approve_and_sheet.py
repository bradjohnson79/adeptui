import json
import urllib.error
import urllib.request

API = "http://127.0.0.1:8758"
PID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1"
CID = "cf4437c7-fd89-4baa-90f3-8098d19eac31"


def post(path):
    req = urllib.request.Request(
        API + path, data=b"{}", headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def get(path):
    with urllib.request.urlopen(API + path, timeout=60) as resp:
        return json.loads(resp.read().decode())


for angle in ("side", "three_quarter", "back"):
    code, body = post(f"/api/projects/{PID}/characters/{CID}/multiview/{angle}/approve")
    slot = ((body.get("multiView") or {}).get("angles") or {}).get(angle) or {}
    print("approve", angle, code, slot.get("approved"), slot.get("assetId"))

code, body = post(f"/api/projects/{PID}/characters/{CID}/multiview/enrich")
print("enrich", code, (body.get("multiviewEnrichment") or {}).get("status") if isinstance(body, dict) else body)

code, body = post(f"/api/projects/{PID}/characters/{CID}/sheet/compose")
print("sheet", code, (body.get("sheet") or {}).get("status") if isinstance(body, dict) else body, (body.get("sheet") or {}).get("assetId") if isinstance(body, dict) else None)

st = get(f"/api/projects/{PID}/characters/{CID}/cc-v2")
print(
    json.dumps(
        {
            "phase": st.get("phase"),
            "schema": st.get("schema"),
            "jsonRevision": st.get("jsonRevision"),
            "front": (st.get("views") or {}).get("front", {}).get("assetId"),
            "angles": {
                name: {
                    "assetId": ((st.get("multiView") or {}).get("angles") or {}).get(name, {}).get("assetId"),
                    "approved": ((st.get("multiView") or {}).get("angles") or {}).get(name, {}).get("approved"),
                }
                for name in ("side", "three_quarter", "back")
            },
            "sheet": (st.get("sheet") or {}).get("assetId"),
        },
        indent=2,
    )
)
