import json
import urllib.request

API = "http://127.0.0.1:8758"
PID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1"


def get(path: str):
    with urllib.request.urlopen(f"{API}{path}", timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


chars = get(f"/api/projects/{PID}/characters")
items = chars.get("items") or chars
print("CHARS", json.dumps([{k: c.get(k) for k in ("id", "name", "slug")} for c in items], indent=2))
for mira in items:
    if "Mira" not in str(mira.get("name") or ""):
        continue
    st = get(f"/api/projects/{PID}/characters/{mira['id']}/cc-v2")
    front = (st.get("views") or {}).get("front") or {}
    print("---", mira["name"], mira["id"])
    print("front", {k: front.get(k) for k in ("status", "approved", "assetId")})
    print("lock", (st.get("visualLock") or {}).get("status"))
    eng = st.get("multiviewEngine") or {}
    print("engine", eng.get("status"), eng.get("available"))
    print("mv", (st.get("multiView") or {}).get("status"))
    print("phase", st.get("phase"))
