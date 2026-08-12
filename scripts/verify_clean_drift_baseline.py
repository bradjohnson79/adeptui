"""Drift baseline for the clean slate — workflow-export topology path verification.

Requires Beta API running with ADEPT_TIMELINE_WORKFLOW_EXPORT=1.

Creates a fresh project + scene + batch, calls the workflow-export endpoint,
and asserts:
  selectedPath=topology
  topologyMatch=true
  bindingsValid=true
  legacyGraphHashCheck=false

Then scans api.log scoped to the current API PID + start timestamp for:
  - a workflowFingerprint line emitted by this process instance
  - zero 'graphHash mismatch' lines in that interval

STOPs (exit 2) if a graphHash mismatch appears for a freshly-created generation,
which would prove a current runtime defect rather than historical residue.

Usage:
    python scripts/verify_clean_drift_baseline.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

API_BASE = "http://127.0.0.1:8758/api"
TL = f"{API_BASE}/director-timeline"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "release-gate" / "clean-beta-baseline"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 8x8 solid PNG for the batch start image.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000080000000808060000008d8d6d"
    "fa0000000149444154789c6360606060606060606060606260606260626062"
    "60626062606260626062606060606000600a3f9f9f9f0100000049454e44ae"
    "426082"
)


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()


def _post(url: str, data: bytes | None = None, multipart: dict | None = None) -> tuple[int, bytes]:
    if multipart:
        boundary = "----drift-baseline-boundary"
        body = b""
        for k, v in multipart.items():
            body += f"--{boundary}\r\n".encode()
            if isinstance(v, dict):  # file part
                body += (
                    f'Content-Disposition: form-data; name="{k}"; filename="{v["name"]}"\r\n'
                    f'Content-Type: {v["mimeType"]}\r\n\r\n'
                ).encode()
                body += v["buffer"]
                body += b"\r\n"
            else:
                body += f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
        if data is not None:
            req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()


def _patch(url: str, data: bytes) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method="PATCH")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()


def _delete(url: str) -> int:
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except Exception:
        return -1


def _create_project() -> str:
    s, b = _post(f"{API_BASE}/projects", json.dumps({"name": "Drift Baseline Test"}).encode())
    assert s == 200, f"create project: {s} {b[:200]}"
    return json.loads(b)["id"]


def _first_scene(pid: str) -> str:
    s, b = _get(f"{API_BASE}/projects/{pid}/scenes")
    assert s == 200, f"list scenes: {s}"
    scenes = json.loads(b)
    slist = scenes if isinstance(scenes, list) else scenes.get("scenes", [])
    assert len(slist) > 0
    return slist[0]["id"]


def _upload_image(pid: str) -> str:
    s, b = _post(
        f"{API_BASE}/projects/{pid}/assets",
        multipart={"file": {"name": "drift.png", "mimeType": "image/png", "buffer": PNG}, "tag": "drift", "kind": "image"},
    )
    assert s == 200, f"upload: {s} {b[:200]}"
    return json.loads(b)["id"]


def _config_batch(pid: str, sid: str, batch_id: str, img_id: str) -> None:
    payload = {
        "generatorId": "ltx-local",
        "plannedDuration": 5,
        "promptSegments": [
            {
                "id": f"ps-{batch_id[-6:]}",
                "start": 0,
                "length": 5,
                "text": "Drift baseline — topology path test",
                "role": "primary",
                "strength": 1,
                "anchorIds": [],
                "executionStrategy": "compiled",
                "versionId": f"psv-{batch_id[-6:]}",
            }
        ],
        "sourceAnchors": [{"kind": "image", "assetId": img_id, "label": "start", "atTime": 0, "strength": 1}],
    }
    s, b = _patch(f"{TL}/projects/{pid}/scenes/{sid}/batches/{batch_id}", json.dumps(payload).encode())
    assert s == 200, f"config batch: {s} {b[:200]}"


def _workflow_export(pid: str, sid: str, batch_id: str) -> dict:
    s, b = _post(f"{TL}/projects/{pid}/scenes/{sid}/batches/{batch_id}/workflow-export")
    if s != 200:
        print(f"FATAL: workflow-export returned {s}: {b.decode('utf-8','replace')[:500]}", file=sys.stderr)
        print("Restart Beta API with ADEPT_TIMELINE_WORKFLOW_EXPORT=1", file=sys.stderr)
        sys.exit(3)
    return json.loads(b)


def _api_pid() -> tuple[int, float]:
    pid_file = REPO_ROOT / "data" / "runtime" / "beta" / "pids" / "api.pid"
    if not pid_file.exists():
        print(f"FATAL: {pid_file} not found", file=sys.stderr)
        sys.exit(3)
    pid = int(pid_file.read_text().strip())
    # Process start time as epoch seconds (for log scoping).
    import subprocess
    r = subprocess.run(["powershell", "-Command", f"(Get-Process -Id {pid}).StartTime | ConvertTo-Json"],
                        capture_output=True, text=True)
    try:
        start_str = json.loads(r.stdout) if r.stdout.strip() else ""
        # PowerShell ConvertTo-Json emits "/Date(epoch_ms)/" or ISO; parse loosely.
        dt = datetime.fromisoformat(str(start_str).replace("Z", "")) if "T" in str(start_str) else datetime.now()
        start_epoch = dt.timestamp()
    except Exception:
        start_epoch = time.time() - 3600  # fallback: look back 1h
    return pid, start_epoch


def _scan_log(pid: int, start_epoch: float) -> dict:
    log_file = REPO_ROOT / "data" / "runtime" / "logs" / "beta" / "api.log"
    if not log_file.exists():
        return {"error": f"{log_file} not found", "fingerprint_lines": 0, "graphhash_mismatch_lines": []}
    fingerprint_lines = 0
    fingerprint_line_text = ""
    mismatch_lines = []
    # Supervisor pump timestamps lines like "[2026-08-08T04:02:14.123456Z] ...".
    # We scope to lines at or after the API process start.
    try:
        with log_file.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", line)
                ts = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").timestamp() if m else 0
                if ts and ts < start_epoch - 60:
                    continue
                if "workflowFingerprint" in line:
                    fingerprint_lines += 1
                    fingerprint_line_text = line.rstrip()
                if "graphHash mismatch" in line:
                    mismatch_lines.append(line.rstrip()[:300])
    except Exception as e:
        return {"error": str(e), "fingerprint_lines": 0, "graphhash_mismatch_lines": []}

    # Parse selectedPath and legacyGraphHashCheck from the workflowFingerprint log line.
    # The line is structured key=value pairs, e.g.:
    #   workflowFingerprint workflow=ltx.simple_i2v selectedPath=topology topologyMatch=true ...
    selected_path = None
    legacy_check = None
    if fingerprint_line_text:
        sp_match = re.search(r"selectedPath=(\S+)", fingerprint_line_text)
        if sp_match:
            selected_path = sp_match.group(1)
        lc_match = re.search(r"legacyGraphHashCheck=(\S+)", fingerprint_line_text)
        if lc_match:
            legacy_check = lc_match.group(1).rstrip(",")
        # Also try JSON-style if the line embeds JSON.
        if selected_path is None:
            try:
                json_match = re.search(r"workflowFingerprint\s*(\{.*\})", fingerprint_line_text)
                if json_match:
                    payload = json.loads(json_match.group(1))
                    selected_path = payload.get("selectedPath")
                    legacy_check = payload.get("legacyGraphHashCheck")
            except Exception:
                pass

    return {
        "fingerprint_lines": fingerprint_lines,
        "fingerprint_line": fingerprint_line_text[:500],
        "selectedPath": selected_path,
        "legacyGraphHashCheck": legacy_check,
        "graphhash_mismatch_lines": mismatch_lines,
    }


def main() -> int:
    pid, start_epoch = _api_pid()
    print(f"[drift] api PID={pid} start_epoch={start_epoch:.0f}")

    pid_created = _create_project()
    result: dict = {"pid": pid, "project_id": pid_created}
    cleanup_failed = False
    try:
        sid = _first_scene(pid_created)
        img_id = _upload_image(pid_created)

        # Get the default batch.
        s, b = _get(f"{TL}/projects/{pid_created}/scenes/{sid}/master")
        assert s == 200
        master = json.loads(b)["master"]
        batch_id = master["batchBlocks"][0]["id"]

        _config_batch(pid_created, sid, batch_id, img_id)

        # Workflow export (the key drift-baseline call).
        export = _workflow_export(pid_created, sid, batch_id)
        print(f"[drift] workflow-export keys: {list(export.keys())}")
        write_path = OUT_DIR / "drift_workflow_export.json"
        write_path.write_text(json.dumps(export, indent=2), encoding="utf-8")
        print(f"[drift] export -> {write_path}")

        # Scan log scoped to this process instance (must run before reading log-derived fields).
        log_scan = _scan_log(pid, start_epoch)

        # Assert required fields. topologyMatch and bindingsValid come from the
        # export payload; selectedPath and legacyGraphHashCheck come from the
        # workflowFingerprint log line emitted by prepare_executable_graph.
        topology_match = export.get("topologyMatch")
        bindings_valid = export.get("bindingsValid")
        selected_path = log_scan.get("selectedPath")
        legacy_check = log_scan.get("legacyGraphHashCheck")

        result.update({
            "scene_id": sid,
            "batch_id": batch_id,
            "selectedPath": selected_path,
            "topologyMatch": topology_match,
            "bindingsValid": bindings_valid,
            "legacyGraphHashCheck": legacy_check,
        })
        print(f"[drift] selectedPath={selected_path} topologyMatch={topology_match} bindingsValid={bindings_valid} legacyGraphHashCheck={legacy_check}")

        result["log_scan"] = log_scan
        print(f"[drift] log: fingerprint_lines={log_scan['fingerprint_lines']} mismatch_lines={len(log_scan['graphhash_mismatch_lines'])}")

        # Write evidence BEFORE verdict so it survives a FAIL return.
        out = OUT_DIR / "drift_baseline_result.json"
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[drift] result -> {out}")

        # Verdict.
        def _as_bool(v):
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.lower() == "true"
            return v
        passed = True
        reasons = []
        if selected_path != "topology":
            passed = False
            reasons.append(f"selectedPath={selected_path} (expected topology)")
        if _as_bool(topology_match) is not True:
            passed = False
            reasons.append(f"topologyMatch={topology_match} (expected true)")
        if _as_bool(bindings_valid) is not True:
            passed = False
            reasons.append(f"bindingsValid={bindings_valid} (expected true)")
        if _as_bool(legacy_check) is not False:
            passed = False
            reasons.append(f"legacyGraphHashCheck={legacy_check} (expected false)")
        if log_scan["graphhash_mismatch_lines"]:
            passed = False
            reasons.append(f"graphHash mismatch appeared for fresh generation: {log_scan['graphhash_mismatch_lines'][:3]}")
            print("[drift] STOP — graphHash mismatch on freshly-created generation = current runtime defect", file=sys.stderr)

        if not passed:
            print("[drift] FAIL: " + "; ".join(reasons), file=sys.stderr)
            return 2
        print("[drift] PASS — topology + bindings contract verified, zero graphHash mismatch")
        return 0
    finally:
        # Cleanup: always attempt to delete the project, even on failure/assertion paths.
        del_status = _delete(f"{API_BASE}/projects/{pid_created}")
        if del_status != 200:
            cleanup_failed = True
            print(f"[drift] WARNING: cleanup delete returned {del_status} for {pid_created}", file=sys.stderr)
        if cleanup_failed:
            print(f"[drift] WARNING: project {pid_created} may still exist — manual cleanup needed", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
