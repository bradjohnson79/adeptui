"""GitHub-first isolated installs for MoGe-2 and VGGT.

Weights: Hugging Face only when authorized. VGGT production weights are
facebook/VGGT-1B-Commercial only. Never facebook/VGGT-1B.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ...setup.essential_agreement import require_essential_agreement
from . import isolated_runtime as iso
from .moge2_runtime import COMPONENT_ID as MOGE_ID
from .moge2_runtime import MOGE_CODE_REPO, runtime_status as moge_status
from .vggt_runtime import COMPONENT_ID as VGGT_ID
from .vggt_runtime import FORBIDDEN_MODEL_ID, VGGT_CODE_REPO, VGGT_MODEL_ID
from .vggt_runtime import assert_commercial_model_only
from .vggt_runtime import runtime_status as vggt_status


def _skip_network_install() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or os.environ.get("ADEPT_SKIP_GEOMETRY_CLONE", "").strip() in {
        "1",
        "true",
        "TRUE",
        "yes",
    }


def install_moge2_source(*, download_weights: bool = False) -> dict[str, Any]:
    require_essential_agreement(MOGE_ID, action="install")
    if _skip_network_install():
        return {
            "ok": True,
            "componentId": MOGE_ID,
            "clone": {"ok": False, "skipped": True, "reason": "test/harness skip"},
            "weights": {"ok": False, "skipped": True},
            "weightsLicense": "unconfirmed",
            "runtime": moge_status(),
            "message": "MoGe-2 install eligible after agreement. Network clone skipped in this harness.",
        }
    src = iso.source_dir("moge2")
    try:
        cloned = iso.clone_github(MOGE_CODE_REPO, src)
    except Exception as exc:  # noqa: BLE001
        cloned = {"ok": False, "error": str(exc)[:400]}
    python = None
    reqs = None
    if cloned.get("ok"):
        try:
            python = str(iso.ensure_venv("moge2"))
            gpu_torch = iso.install_gpu_torch("moge2")
            requirements = src / "requirements.txt"
            reqs = iso.install_requirements("moge2", requirements) if requirements.is_file() else {"ok": True, "skipped": True}
            reqs = {**(reqs if isinstance(reqs, dict) else {}), "gpuTorch": gpu_torch}
        except Exception as exc:  # noqa: BLE001
            reqs = {"ok": False, "error": str(exc)[:400]}
    weights = {"ok": False, "skipped": True, "reason": "Mission B downloads official HF weights only when explicitly authorized."}
    if download_weights and cloned.get("ok"):
        weights = _download_moge_weights()
    status = moge_status()
    return {
        "ok": bool(cloned.get("ok")),
        "componentId": MOGE_ID,
        "clone": cloned,
        "venvPython": python,
        "requirements": reqs,
        "weights": weights,
        "weightsLicense": "unconfirmed",
        "runtime": status,
        "message": (
            "MoGe-2 source prepared. Weight terms remain unconfirmed. "
            "Clone is not Ready."
        ),
    }


def install_vggt_source(*, download_weights: bool = False, model_id: str = VGGT_MODEL_ID) -> dict[str, Any]:
    require_essential_agreement(VGGT_ID, action="install")
    assert_commercial_model_only(model_id)
    if _skip_network_install():
        return {
            "ok": True,
            "componentId": VGGT_ID,
            "clone": {"ok": False, "skipped": True, "reason": "test/harness skip"},
            "weights": {
                "ok": False,
                "skipped": True,
                "status": "MODEL_ACCESS_GATED",
                "modelId": VGGT_MODEL_ID,
                "forbidden": FORBIDDEN_MODEL_ID,
            },
            "runtime": vggt_status(),
            "message": "VGGT install eligible after agreement. Commercial weights remain gated. Network clone skipped in this harness.",
        }
    src = iso.source_dir("vggt")
    try:
        cloned = iso.clone_github(VGGT_CODE_REPO, src)
    except Exception as exc:  # noqa: BLE001
        cloned = {"ok": False, "error": str(exc)[:400]}
    python = None
    reqs = None
    if cloned.get("ok"):
        try:
            python = str(iso.ensure_venv("vggt"))
            requirements = src / "requirements.txt"
            reqs = iso.install_requirements("vggt", requirements) if requirements.is_file() else {"ok": True, "skipped": True}
        except Exception as exc:  # noqa: BLE001
            reqs = {"ok": False, "error": str(exc)[:400]}
    weights: dict[str, Any]
    if download_weights:
        weights = _download_vggt_commercial_weights(model_id)
    else:
        weights = {
            "ok": False,
            "skipped": True,
            "status": "MODEL_ACCESS_GATED",
            "modelId": VGGT_MODEL_ID,
            "forbidden": FORBIDDEN_MODEL_ID,
        }
    status = vggt_status()
    return {
        "ok": bool(cloned.get("ok")),
        "componentId": VGGT_ID,
        "clone": cloned,
        "venvPython": python,
        "requirements": reqs,
        "weights": weights,
        "runtime": status,
        "message": (
            "VGGT GitHub source may be cloned. Commercial model access stays gated "
            "until facebook/VGGT-1B-Commercial weights exist. Clone is not Ready."
        ),
    }


def _download_moge_weights() -> dict[str, Any]:
    dest = iso.runtime_root("moge2") / "weights"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"huggingface_hub unavailable: {exc}"}
    try:
        path = snapshot_download(
            repo_id="Ruicheng/moge-2-vitl-normal",
            local_dir=str(dest / "moge-2-vitl-normal"),
        )
        return {
            "ok": True,
            "path": path,
            "repo": "Ruicheng/moge-2-vitl-normal",
            "weightsLicense": "unconfirmed",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:400], "weightsLicense": "unconfirmed"}


def _download_vggt_commercial_weights(model_id: str) -> dict[str, Any]:
    assert_commercial_model_only(model_id)
    dest = iso.runtime_root("vggt") / "weights" / "VGGT-1B-Commercial"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"huggingface_hub unavailable: {exc}", "status": "MODEL_ACCESS_GATED"}
    try:
        path = snapshot_download(repo_id=VGGT_MODEL_ID, local_dir=str(dest))
        return {"ok": True, "path": path, "modelId": VGGT_MODEL_ID}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc)[:400],
            "status": "MODEL_ACCESS_GATED",
            "modelId": VGGT_MODEL_ID,
        }


def worker_script(name: str) -> Path:
    return Path(__file__).resolve().parent / "workers" / f"{name}_infer_worker.py"
