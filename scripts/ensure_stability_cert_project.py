"""Create or reuse the named Adept Stability Cert project. Never uses Schnick/Korri."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CERT_NAME = "Adept Stability Cert"
SCHNICK = "2347bf46-3762-4763-86c5-4a6032522278"
API = os.environ.get("STUDIO_API_BASE", "http://127.0.0.1:8758").rstrip("/")
OUT = Path(__file__).resolve().parents[1] / "data" / "runtime" / "stability-cert-project.json"


def _req(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    try:
        projects = _req("GET", f"{API}/api/projects")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Studio API not reachable at {API}: {exc}", file=sys.stderr)
        return 2
    rows = projects if isinstance(projects, list) else projects.get("projects") or []
    found = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("name") or "") == CERT_NAME:
            found = row
            break
    if found and str(found.get("id") or "") == SCHNICK:
        print("Refusing to reuse Schnick as the cert project.", file=sys.stderr)
        return 3
    if not found:
        found = _req("POST", f"{API}/api/projects", {"name": CERT_NAME})
    pid = str(found.get("id") or found.get("projectId") or "")
    if not pid or pid == SCHNICK:
        print("Cert project id invalid.", file=sys.stderr)
        return 3
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"id": pid, "name": CERT_NAME}, indent=2), encoding="utf-8")
    print(pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
