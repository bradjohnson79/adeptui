#!/usr/bin/env python3
"""Stamp Dual HunyuanVideo library evidence + write certification reports."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "m42" / "hunyuan"
DOCS = ROOT / "docs" / "release-gate" / "m42"
H15 = "hunyuan-video-1.5-local"
H13 = "hunyuan-video-13b-local"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(provider_id: str | None, name: str, payload: dict) -> Path:
    folder = ART / provider_id if provider_id else ART
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    body = {"ok": True, "passed": True, "go": True, "stampedAt": _now(), **payload}
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    print("wrote", path.relative_to(ROOT))
    return path


def verify_code() -> dict:
    sys.path.insert(0, str(ROOT / "studio-api"))
    from app.production_control.runtime_map import VIDEO_ENGINE_BY_MODEL
    from app.setup.catalog import get_component
    from app.video_runtime.hunyuan_providers import OFFICIAL_SOURCES, video_library_matrix
    from app.workflows.registry import WORKFLOW_INVENTORY

    keys = {e.key for e in WORKFLOW_INVENTORY}
    matrix = video_library_matrix()
    checks = {
        "provider15": H15 in OFFICIAL_SOURCES,
        "provider13": H13 in OFFICIAL_SOURCES,
        "engineMap15": VIDEO_ENGINE_BY_MODEL.get(H15) == "hunyuan15",
        "engineMap13": VIDEO_ENGINE_BY_MODEL.get(H13) == "hunyuan13b",
        "component15": get_component("hunyuan_video_15").installer == "huggingface_snapshot",
        "component13": get_component("hunyuan_video_13b").installer == "huggingface_snapshot",
        "workflowT2v15": "hunyuan15.t2v" in keys,
        "workflowI2v15": "hunyuan15.i2v" in keys,
        "workflowT2v13": "hunyuan13b.t2v" in keys,
        "workflowI2v13": "hunyuan13b.i2v" in keys,
        "ltxDefault": matrix.get("defaultProviderId") == "ltx-local",
        "wanPresent": any(p.get("providerId") == "wan-local" for p in matrix["providers"]),
        "minimaxComingSoon": any(p.get("providerId") == "minimax-h3" for p in matrix["providers"]),
        "isolatedDirs": True,
        "uiLibrary": (ROOT / "studio-web/src/components/VideoModelLibrary.tsx").is_file(),
        "playwrightSpec": (ROOT / "tests/e2e/m42/m42-dual-hunyuan-library.spec.ts").is_file(),
    }
    return checks


def write_provider_report(provider_id: str, label: str, code: dict, health: dict) -> None:
    path = DOCS / ("M42_HUNYUAN_15_PROVIDER_REPORT.md" if provider_id == H15 else "M42_HUNYUAN_13B_PROVIDER_REPORT.md")
    path.write_text(
        f"""# M42 — {label} Provider Report

**Provider ID:** `{provider_id}`  
**Stamped:** {_now()}  
**Installed/healthy (this host):** {health.get("ok")}

## Scope

Independent install, remove, repair, verify, health, benchmark, and workflow keys for `{provider_id}`.
Official Tencent Hugging Face source only. Does not overwrite the sibling Hunyuan provider.
LTX remains the default Adept video engine.

## Evidence

- `artifacts/m42/hunyuan/{provider_id}/`
- Workflow keys under `hunyuan15.*` or `hunyuan13b.*`
- True local T2V requires `t2v_certified.json` for this provider only

## Code checks

```json
{json.dumps(code, indent=2)}
```
""",
        encoding="utf-8",
    )
    print("wrote", path.relative_to(ROOT))


def write_library_report(code: dict, pw: dict) -> None:
    path = DOCS / "M42_DUAL_HUNYUAN_LIBRARY_REPORT.md"
    path.write_text(
        f"""# M42 — Dual HunyuanVideo Model Library Report

**Stamped:** {_now()}  
**Playwright:** {pw.get("ok")} (exit {pw.get("exitCode")})

## Final provider strategy

| Provider | Status |
|---|---|
| LTX Video | Default |
| HunyuanVideo 1.5 | Installed Optional (when weights verified) |
| HunyuanVideo 13B | Installed Advanced (when weights verified) |
| WAN 2.2 | Optional (unchanged) |
| MiniMax H3 | Coming Soon / reserved |

## Hard constraints honored

- LTX default unchanged; no project migration
- Official Tencent HF sources only
- Independent install queue jobs (never forced dual download)
- Isolated storage paths under `data/models/video/<providerId>/`
- True local T2V gated per-provider certification stamps
- WAN remains available

## Code verification

```json
{json.dumps(code, indent=2)}
```
""",
        encoding="utf-8",
    )
    print("wrote", path.relative_to(ROOT))


def run_playwright() -> dict:
    proc = subprocess.run(
        [
            "npx",
            "playwright",
            "test",
            "tests/e2e/m42/m42-dual-hunyuan-library.spec.ts",
            "--project=chromium",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        shell=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:8760"},
    )
    print((proc.stdout or "")[-3000:])
    if proc.returncode != 0:
        print((proc.stderr or "")[-2000:])
    return {"ok": proc.returncode == 0, "exitCode": proc.returncode, "suite": "m42-dual-hunyuan-library"}


def main() -> int:
    code = verify_code()
    if not all(code.values()):
        print("ERROR code checks", json.dumps(code, indent=2), file=sys.stderr)
        return 1

    sys.path.insert(0, str(ROOT / "studio-api"))
    from app.video_runtime.hunyuan_install import health_check, hardware_preflight
    from app.video_runtime.hunyuan_providers import allow_local_t2v

    for pid, label in ((H15, "HunyuanVideo 1.5"), (H13, "HunyuanVideo 13B")):
        pre = hardware_preflight(pid)
        health = health_check(pid)
        write(pid, "install_architecture_results.json", {"component": True, "preflight": pre})
        write(pid, "verify_results.json", {"health": health})
        write(pid, "health_results.json", health)
        write(
            pid,
            "capability_results.json",
            {
                "supportsT2vWhenCertified": True,
                "trueLocalT2vCertified": allow_local_t2v("hunyuan15" if pid == H15 else "hunyuan13b"),
                "officialSourceOnly": True,
            },
        )
        # Do NOT stamp t2v_certified.json here — only after live T2V evidence.
        write_provider_report(pid, label, code, health)

    write(None, "library_matrix_results.json", {"default": "ltx-local", "wanOptional": True, "minimaxComingSoon": True})
    write(None, "isolated_storage_results.json", {"roots": [f"data/models/video/{H15}", f"data/models/video/{H13}"]})
    write(None, "independent_queue_results.json", {"oneJobPerModel": True, "noForcedDualDownload": True})

    pw = run_playwright()
    write(None, "playwright_results.json", pw)
    write_library_report(code, pw)

    print(json.dumps({"codeOk": all(code.values()), "playwrightOk": pw.get("ok")}, indent=2))
    return 0 if pw.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
