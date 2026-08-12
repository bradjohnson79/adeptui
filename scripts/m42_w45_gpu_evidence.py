#!/usr/bin/env python3
"""Capture CUDA/GPU evidence for M42 W45 Audio Studio ACE-Step repair."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "m42" / "w45" / "gpu-evidence"
API = "http://127.0.0.1:8758"
ACE_PY = ROOT / "data" / "m210b-ace-venv" / "Scripts" / "python.exe"
WORKER = ROOT / "studio-api" / "app" / "codirector" / "native_audio" / "ace_step_worker.py"
CKPT = ROOT / "data" / "m210b-sandbox" / "providers" / "m2101-music-045" / "models"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(name: str, payload: object) -> Path:
    ART.mkdir(parents=True, exist_ok=True)
    path = ART / name
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")
    print(f"wrote {path}")
    return path


def req(method: str, path: str, body: dict | None = None, timeout: float = 120.0):
    data = None if body is None else json.dumps(body).encode("utf-8")
    r = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        return e.code, payload


def probe_worker_cuda() -> dict:
    script = (
        "import json,torch;"
        "print(json.dumps({"
        "'torch_version': torch.__version__,"
        "'cuda_available': bool(torch.cuda.is_available()),"
        "'device_count': int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,"
        "'device_name': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,"
        "'selected_device': 'cuda:0' if torch.cuda.is_available() else 'cpu'"
        "}))"
    )
    proc = subprocess.run([str(ACE_PY), "-c", script], capture_output=True, text=True, timeout=120)
    out = {"ok": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}
    try:
        out["probe"] = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except Exception:
        out["probe"] = None
    return out


def main() -> int:
    timeline: list[dict] = [{"at": now(), "stage": "start"}]
    cuda_probe = probe_worker_cuda()
    write("01_worker_venv_cuda_probe.json", {"at": now(), **cuda_probe})
    timeline.append({"at": now(), "stage": "worker_venv_cuda_probe", "probe": cuda_probe.get("probe")})

    # Direct worker smoke (device + cpu_offload evidence in stdout phases)
    out_wav = ART / f"direct_worker_{int(time.time())}.wav"
    cmd = [
        str(ACE_PY),
        str(WORKER),
        "--prompt",
        "Warm hopeful cinematic bed soft piano evidence pass",
        "--duration",
        "6",
        "--out",
        str(out_wav),
        "--seed",
        "7",
        "--checkpoint_dir",
        str(CKPT),
        "--device_id",
        "0",
        "--infer_step",
        "12",
        "--cpu_offload",
        "0",
    ]
    # Start nvidia-smi logger
    smi_log = ART / "nvidia_smi_during_job.log"
    smi_proc = subprocess.Popen(
        ["nvidia-smi", "-l", "1"],
        stdout=open(smi_log, "w", encoding="utf-8", errors="replace"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    timeline.append({"at": now(), "stage": "nvidia_smi_started", "log": str(smi_log)})

    # Audio Studio API generate (async) — UI→API→queue→worker path
    code, projects = req("GET", "/api/projects", timeout=30)
    plist = projects if isinstance(projects, list) else (projects or {}).get("projects") or []
    if code != 200 or not plist:
        smi_proc.terminate()
        write("FAIL.json", {"error": "no projects", "code": code})
        return 1
    project_id = plist[0]["id"]
    timeline.append({"at": now(), "stage": "ui_api_project", "projectId": project_id})

    t_api = now()
    code, batch = req(
        "POST",
        f"/api/audio-studio/projects/{project_id}/generate",
        {
            "kind": "music",
            "prompt": "Warm hopeful cinematic rise soft piano strings evidence",
            "durationSeconds": 8,
            "mood": ["hopeful"],
            "candidateCount": 1,
            "asyncMode": True,
        },
        timeout=60,
    )
    timeline.append({"at": t_api, "stage": "api_generate_submitted", "http": code, "batchId": (batch or {}).get("id")})
    if code != 200 or not batch.get("id"):
        smi_proc.terminate()
        write("FAIL.json", {"error": "generate failed", "http": code, "body": batch})
        return 2

    batch_id = batch["id"]
    write("02_batch_started.json", {"at": now(), "batch": batch})

    # Also kick a short direct worker run in parallel? Prefer sequential for clearer smi attribution.
    # Poll API batch to completion while smi runs.
    final_batch = None
    for i in range(120):
        time.sleep(2)
        c, b = req("GET", f"/api/audio-studio/projects/{project_id}/batches/{batch_id}", timeout=30)
        if c == 200:
            final_batch = b
            st = str(b.get("status") or "")
            timeline.append(
                {
                    "at": now(),
                    "stage": "queue_poll",
                    "i": i,
                    "status": st,
                    "progress": b.get("progress"),
                }
            )
            if st in ("complete", "failed", "cancelled"):
                break

    write("03_batch_final.json", {"at": now(), "batch": final_batch})

    # Capture one nvidia-smi snapshot and stop logger
    snap = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=30)
    write("04_nvidia_smi_snapshot.txt", snap.stdout or snap.stderr or "")
    try:
        smi_proc.terminate()
        smi_proc.wait(timeout=5)
    except Exception:
        pass

    # Direct worker evidence for device/cpu_offload phases (explicit)
    t_worker = now()
    timeline.append({"at": t_worker, "stage": "direct_worker_start"})
    wproc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    phases = []
    for line in (wproc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            phases.append(json.loads(line))
        except Exception:
            pass
    write(
        "05_direct_worker_run.json",
        {
            "at": now(),
            "returncode": wproc.returncode,
            "phases": phases,
            "stdoutTail": (wproc.stdout or "")[-4000:],
            "stderrTail": (wproc.stderr or "")[-2000:],
            "outExists": out_wav.is_file(),
            "outBytes": out_wav.stat().st_size if out_wav.is_file() else 0,
        },
    )
    timeline.append({"at": now(), "stage": "direct_worker_done", "returncode": wproc.returncode, "phases": phases})

    # Approve / library / place
    cands = (final_batch or {}).get("candidates") or []
    ready = next((c for c in cands if c.get("status") == "ready" and c.get("asset_id")), None)
    approve = select = place = library = None
    if ready:
        sc, select = req(
            "POST",
            f"/api/audio-studio/projects/{project_id}/batches/{batch_id}/candidates/{ready['id']}/select",
        )
        ac, approve = req(
            "POST",
            f"/api/audio-studio/projects/{project_id}/batches/{batch_id}/candidates/{ready['id']}/approve",
        )
        pc, place = req(
            "POST",
            f"/api/audio-studio/projects/{project_id}/place",
            {"assetId": ready["asset_id"], "category": "music", "startMs": 0, "loop": False},
        )
        lc, library = req("GET", f"/api/projects/{project_id}/library", timeout=60)
        timeline.append(
            {
                "at": now(),
                "stage": "approve_library_place",
                "selectHttp": sc,
                "approveHttp": ac,
                "placeHttp": pc,
                "libraryHttp": lc,
                "assetId": ready["asset_id"],
            }
        )

    # Provider resolver honesty
    _, providers = req("GET", f"/api/audio-studio/projects/{project_id}/providers?kind=music")
    write("06_providers.json", providers)

    device_phase = next((p for p in phases if p.get("phase") == "device"), {})
    model_phase = next((p for p in phases if p.get("phase") == "model_device"), {})
    final_meta = next((p for p in reversed(phases) if p.get("ok") is True), {})

    evidence = {
        "at": now(),
        "ok": bool(
            (cuda_probe.get("probe") or {}).get("cuda_available")
            and device_phase.get("cuda_available") is True
            and device_phase.get("selected_device") == "cuda:0"
            and device_phase.get("cpu_offload") is False
            and (final_batch or {}).get("status") == "complete"
            and ready
            and approve
            and approve.get("approved") is True
            and place
            and place.get("ok") is True
            and out_wav.is_file()
        ),
        "checks": {
            "torch_cuda_is_available": (cuda_probe.get("probe") or {}).get("cuda_available"),
            "torch_cuda_device_count": (cuda_probe.get("probe") or {}).get("device_count"),
            "torch_cuda_get_device_name_0": (cuda_probe.get("probe") or {}).get("device_name"),
            "worker_selected_device": device_phase.get("selected_device") or final_meta.get("selected_device"),
            "worker_cpu_offload": device_phase.get("cpu_offload"),
            "worker_model_device": model_phase.get("model_device") or final_meta.get("model_device"),
            "batch_status": (final_batch or {}).get("status"),
            "candidate_ready": bool(ready),
            "asset_id": (ready or {}).get("asset_id"),
            "approved": bool(approve and approve.get("approved")),
            "placed": bool(place and place.get("ok")),
            "direct_wav_bytes": out_wav.stat().st_size if out_wav.is_file() else 0,
            "nvidia_smi_log": str(smi_log),
        },
        "timeline": timeline,
    }
    write("07_evidence_summary.json", evidence)
    write("timeline.json", timeline)
    print(json.dumps({"ok": evidence["ok"], "checks": evidence["checks"]}, indent=2))
    return 0 if evidence["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
