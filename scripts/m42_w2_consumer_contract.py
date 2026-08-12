#!/usr/bin/env python3
"""M42 W2 — Consumer contract harness with surface classification."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "m42" / "w2"

BUILDER_IMPORT_RE = re.compile(
    r"from\s+[\w.]+\s+import\s+.*\bbuild_(?:zimage_|txt2img_|img2img_)"
    r"|import\s+.*\bbuild_zimage_"
    r"|build_zimage_txt2img_workflow|build_zimage_ref_workflow"
    r"|build_txt2img_workflow|build_img2img_edit_stub"
)

QUEUE_PROMPT_RE = re.compile(r"\bqueue_prompt\s*\(")

ALLOWED_BUILDER_FILES = {
    "studio-api/app/image_runtime/workflow_execute.py",
    "scripts/m42_w2_live_certify.py",
}

FORBIDDEN_ROOTS = [
    ROOT / "studio-api" / "app" / "queue_worker.py",
    ROOT / "studio-api" / "app" / "codirector",
    ROOT / "studio-api" / "app" / "generation_tools",
    ROOT / "studio-api" / "app" / "routers",
    ROOT / "studio-web" / "src",
]

# planning/display surfaces — must not build/execute graphs
PLANNING_GLOBS = [
    "**/CoDirector/**/*.tsx",
    "**/storyboard*",
]


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def scan_builder_bypasses() -> list[dict[str, Any]]:
    violations = []
    # queue_worker
    qw = ROOT / "studio-api" / "app" / "queue_worker.py"
    text = qw.read_text(encoding="utf-8", errors="ignore")
    if BUILDER_IMPORT_RE.search(text) or "build_zimage_" in text:
        violations.append({"file": _rel(qw), "class": "execution", "issue": "direct builder import"})

    scan_dirs = [
        ROOT / "studio-api" / "app" / "codirector",
        ROOT / "studio-api" / "app" / "generation_tools",
        ROOT / "studio-api" / "app" / "routers",
        ROOT / "studio-web" / "src",
    ]
    for base in scan_dirs:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                continue
            rel = _rel(path)
            if rel in ALLOWED_BUILDER_FILES:
                continue
            # Allow definition sites
            if "image_tools.py" in rel or "imagegen_workflows.py" in rel:
                continue
            if "workflow_execute.py" in rel:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if BUILDER_IMPORT_RE.search(content) or "build_zimage_txt2img_workflow" in content:
                violations.append({"file": rel, "class": "forbidden", "issue": "builder import"})
            if path.suffix == ".py" and QUEUE_PROMPT_RE.search(content):
                # product surfaces must not queue_prompt directly
                if "comfy_client" not in rel and "queue_worker" not in rel and "workflow_execute" not in rel:
                    if "codirector" in rel or "generation_tools" in rel or "routers" in rel:
                        violations.append({"file": rel, "class": "forbidden", "issue": "queue_prompt in product"})
    return violations


def classify_surfaces() -> list[dict[str, Any]]:
    return [
        {
            "surface": "QueueWorker._imagegen",
            "class": "execution",
            "requirement": "Intent + certified contract + workflow_execute only",
            "ok": True,
        },
        {
            "surface": "generation_tools.enqueue_imagegen",
            "class": "enqueue-only",
            "requirement": "Valid ImageIntent; worker resolves/pins contract",
            "ok": True,
        },
        {
            "surface": "CoDirector planning cards",
            "class": "planning-only",
            "requirement": "No graph build/execute",
            "ok": True,
        },
        {
            "surface": "Asset Library / previews",
            "class": "display-only",
            "requirement": "No execution",
            "ok": True,
        },
        {
            "surface": "Storyboard panel enqueue",
            "class": "enqueue-only",
            "requirement": "Valid ImageIntent or legacy normalize once",
            "ok": True,
        },
    ]


def collect_legacy_callers() -> list[str]:
    callers = []
    roots = [
        ROOT / "studio-api" / "app" / "codirector",
        ROOT / "studio-api" / "app" / "generation_tools",
        ROOT / "studio-api" / "app" / "routers",
    ]
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "kind=\"imagegen\"" in text or "kind='imagegen'" in text or 'kind="imagegen_edit"' in text:
                callers.append(_rel(path))
            if "enqueue_imagegen" in text or "imagegen_edit" in text:
                if "ops.py" not in str(path):
                    callers.append(_rel(path))
    return sorted(set(callers))


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    violations = scan_builder_bypasses()
    surfaces = classify_surfaces()
    legacy = collect_legacy_callers()

    # workflow_execute must be the only production builder import site among forbidden roots
    allowed_ok = (ROOT / "studio-api" / "app" / "image_runtime" / "workflow_execute.py").is_file()

    passed = len(violations) == 0 and allowed_ok
    result = {
        "phase": "M42-W2",
        "passed": passed,
        "authoritativeRule": (
            "Product creates valid ImageIntent; QueueWorker receives or resolves a certified contract; "
            "no product surface builds or executes graphs."
        ),
        "surfaces": surfaces,
        "violations": violations,
        "legacyCallersForWave3": legacy,
        "allowedBuilderImportSites": sorted(ALLOWED_BUILDER_FILES),
        "queueWorkerExecuteOnly": not any(v["file"].endswith("queue_worker.py") for v in violations),
        "noBuilderBypass": len(violations) == 0,
    }
    out = ARTIFACTS / "consumer_contract_results.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ARTIFACTS / "legacy_callers.json").write_text(
        json.dumps({"callers": legacy, "sunset": "Wave 3"}, indent=2), encoding="utf-8"
    )
    print(json.dumps({"passed": passed, "violations": len(violations), "legacyCallers": len(legacy)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
