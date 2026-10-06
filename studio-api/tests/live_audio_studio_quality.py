"""Live Audio Studio quality + timing suite on Korri Anadriya.

Never creates a project. Writes artifacts under artifacts/audio-studio-quality.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0"
API = "http://127.0.0.1:8758"
OUT = Path("artifacts/audio-studio-quality")

SUITE = [
    {
        "id": "footsteps",
        "kind": "sfx",
        "eventType": "footsteps",
        "prompt": "Footsteps on metal grating, mid-distance.",
        "duration": 3,
        "intensity": "Normal",
        "takes": 2,
    },
    {
        "id": "explosion",
        "kind": "sfx",
        "eventType": "explosion",
        "prompt": "Heavy spaceship explosion in outer space.",
        "duration": 3,
        "intensity": "Bold",
        "takes": 1,
    },
    {
        "id": "door_slam",
        "kind": "sfx",
        "eventType": "door_slam",
        "prompt": "Heavy steel door slam, close.",
        "duration": 2,
        "intensity": "Bold",
        "takes": 1,
    },
    {
        "id": "glass_place",
        "kind": "sfx",
        "eventType": "glass_place",
        "prompt": "Glass placed on a counter, short and clean.",
        "duration": 2,
        "intensity": "Normal",
        "takes": 1,
    },
    {
        "id": "electrical_spark",
        "kind": "sfx",
        "eventType": "electrical_spark",
        "prompt": "Electrical spark and arcing.",
        "duration": 2,
        "intensity": "Bold",
        "takes": 1,
    },
    {
        "id": "ventilation",
        "kind": "ambience",
        "eventType": "ambience",
        "prompt": "Ship ventilation ambience, continuous mechanical environmental bed.",
        "duration": 8,
        "intensity": "Quiet",
        "takes": 1,
    },
]


def req(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail[:1500]}") from exc


def wait_batch(batch_id: str, timeout_sec: float = 900) -> dict:
    started = time.time()
    last = {}
    while time.time() - started < timeout_sec:
        last = req("GET", f"/api/audio-studio/projects/{PROJECT_ID}/batches/{batch_id}")
        status = str(last.get("status") or "")
        if status in ("complete", "failed", "cancelled"):
            return last
        time.sleep(2)
    raise TimeoutError(f"batch {batch_id} still {last.get('status')}")


def analyze_wav(path: Path) -> dict:
    import subprocess
    import sys

    sfx_py = Path("data/m210b-sfx-venv/Scripts/python.exe")
    py = str(sfx_py) if sfx_py.is_file() else sys.executable
    code = r"""
import json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
p = Path(sys.argv[1])
data, sr = sf.read(str(p), always_2d=True)
mono = np.asarray(data, dtype=float).mean(axis=1)
duration = float(mono.size) / float(sr or 1)
peak = float(np.max(np.abs(mono))) if mono.size else 0.0
rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
win = max(1, int(sr * 0.02))
env = np.convolve(np.square(mono), np.ones(win) / win, mode="same")
thresh = max(float(np.max(env)) * 0.25, 1e-8)
peaks = []
i = 1
while i < env.size - 1:
    if env[i] >= thresh and env[i] >= env[i - 1] and env[i] >= env[i + 1]:
        peaks.append(round(i / float(sr), 3))
        i += int(sr * 0.12)
        continue
    i += 1
print(json.dumps({
    "durationSec": duration,
    "sampleRate": int(sr),
    "peak": peak,
    "rms": rms,
    "onsetCount": len(peaks),
    "onsets": peaks[:16],
    "maxEnvelope": float(np.max(env)) if env.size else 0.0,
}))
"""
    proc = subprocess.run([py, "-c", code, str(path)], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout or "")[-400:]}
    return json.loads(proc.stdout.strip().splitlines()[-1])
    arr = np.asarray(data, dtype=float)
    mono = arr.mean(axis=1)
    duration = float(mono.size) / float(sr or 1)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
    win = max(1, int(sr * 0.02))
    env = np.convolve(np.square(mono), np.ones(win) / win, mode="same")
    thresh = max(float(np.max(env)) * 0.25, 1e-8)
    peaks = []
    i = 1
    while i < env.size - 1:
        if env[i] >= thresh and env[i] >= env[i - 1] and env[i] >= env[i + 1]:
            peaks.append(i / float(sr))
            i += int(sr * 0.12)
            continue
        i += 1
    return {
        "durationSec": duration,
        "sampleRate": int(sr),
        "peak": peak,
        "rms": rms,
        "onsetCount": len(peaks),
        "onsets": peaks[:16],
        "maxEnvelope": float(np.max(env)) if env.size else 0.0,
    }


def copy_asset(asset_id: str, dest: Path) -> Path | None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(f"{API}/api/projects/{PROJECT_ID}/assets/{asset_id}/file", timeout=60) as resp:
            dest.write_bytes(resp.read())
        return dest
    except Exception as exc:
        print(f"copy failed {asset_id}: {exc}")
        return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    health = req("GET", "/api/healthz")
    print("health", health.get("ok") or health)
    report: dict = {"projectId": PROJECT_ID, "runs": [], "startedAt": time.time()}
    for i, spec in enumerate(SUITE):
        print(f"\n=== {spec['id']} takes={spec['takes']} ===")
        t0 = time.time()
        started = req(
            "POST",
            f"/api/audio-studio/projects/{PROJECT_ID}/generate",
            {
                "kind": spec["kind"],
                "prompt": spec["prompt"],
                "durationSeconds": spec["duration"],
                "intensity": spec["intensity"],
                "eventType": spec["eventType"],
                "category": spec["kind"],
                "candidateCount": spec["takes"],
                "asyncMode": True,
                "allowProviderSwitch": False,
                "allowCpuFallback": False,
            },
        )
        batch_id = str(started.get("id") or "")
        compiler = started.get("sound_compiler") or {}
        print("raw", compiler.get("raw_prompt"))
        print("compiled", (started.get("compiled_prompt") or compiler.get("compiled_prompt") or "")[:400])
        print("negative", started.get("negative_prompt") or compiler.get("negative_prompt"))
        done = wait_batch(batch_id)
        elapsed = time.time() - t0
        takes = []
        for cand in done.get("candidates") or []:
            asset_id = cand.get("asset_id")
            wav = None
            analysis = None
            if asset_id:
                wav = copy_asset(asset_id, OUT / f"{spec['id']}_{cand.get('id')}.wav")
                if wav and wav.is_file():
                    analysis = analyze_wav(wav)
            takes.append(
                {
                    "id": cand.get("id"),
                    "status": cand.get("status"),
                    "error": cand.get("error"),
                    "assetId": asset_id,
                    "timings": cand.get("timings"),
                    "prompt": cand.get("prompt"),
                    "wav": str(wav) if wav else None,
                    "analysis": analysis,
                    "wavValidation": cand.get("wav_validation"),
                }
            )
        row = {
            "id": spec["id"],
            "batchId": batch_id,
            "elapsedSec": elapsed,
            "status": done.get("status"),
            "progress": done.get("progress"),
            "compiler": compiler,
            "compiledPrompt": done.get("compiled_prompt") or started.get("compiled_prompt"),
            "negativePrompt": done.get("negative_prompt"),
            "rawPrompt": done.get("raw_prompt"),
            "takes": takes,
            "firstOfSuite": i == 0,
        }
        report["runs"].append(row)
        print(json.dumps({k: row[k] for k in ("id", "elapsedSec", "status")}, indent=2))
        for take in takes:
            print(" take", take["status"], take.get("analysis"), take.get("timings"))

    if len(report["runs"]) >= 2:
        report["coldFirstElapsedSec"] = report["runs"][0]["elapsedSec"]
        report["warmLaterElapsedSec"] = [r["elapsedSec"] for r in report["runs"][1:]]
    (OUT / "live-quality-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", OUT / "live-quality-report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
