"""Isolated install roots — never overwrite LTX / WAN / Hunyuan."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any

from ...config import settings

VIDEOCHAT3_HF_ID = "MCG-NJU/VideoChat3-4B"
VIDEOCHAT3_REVISION = "37fa901ec5913f84bc31108ebc1e60ad1903634c"
INTERNVIDEO3_HF_ID = "yanziang/InternVideo3-8B-Instruct"
INTERNVIDEO3_REVISION = "c4602918b65225650d152db2850fe34e01d21fcd"

VIDEOCHAT3_MARKERS = ("config.json", "model.safetensors.index.json")
INTERNVIDEO3_MARKERS = ("config.json", "model.safetensors.index.json")

# Live HF tree at VIDEOCHAT3_REVISION (2026-08-20 reconfirm). LFS oid = SHA-256.
VIDEOCHAT3_POLL_SHA256 = {
    "config.json": "d855aa0d9c6b6f223c9a293b9f1617a877a1ed0fb68a106ffcc084226ab3bf57",
    "model.safetensors.index.json": "4d1a7577864c34d198fcc1812ede1d74798dd673588d085b1811f4516dc91593",
}
VIDEOCHAT3_WEIGHT_SHA256 = {
    "model-0001-others-save_rank0.safetensors": "4c173466ec6a2c5e1544859021fbeac825067ccd54e80b887372d83b1c281654",
    "model-0002-others-save_rank0.safetensors": "322af91f1ba81f290cee20d66bf0841be4826091e6e942688243b38bbc26e597",
    "model-0003-others-save_rank0.safetensors": "1c16eb013f0224c018db06148e28ee60bc1e2b47b1fffde0e311ed9debd63b90",
}
VIDEOCHAT3_WEIGHT_BYTES = {
    "model-0001-others-save_rank0.safetensors": 4252181336,
    "model-0002-others-save_rank0.safetensors": 4288942328,
    "model-0003-others-save_rank0.safetensors": 403726088,
}
# Files executed via trust_remote_code=True. SHA-256 of the pinned-revision blobs.
VIDEOCHAT3_REMOTE_CODE_SHA256 = {
    "modeling_videochat3.py": "853a76844c94612f350f222247983e734d70ebe37fc6778a4b3ea0e22bdc36f8",
    "configuration_videochat3.py": "b2c6fe79f9fc9ac75466dc9be6cf2b95a530f6c1a06638bf87ae75289444d02e",
    "processing_videochat3.py": "2cf662dca1391ad133ef80dad5cbb6505a0e30e3564881f6174dc6633e2c3696",
    "video_processing_videochat3.py": "bf33cff1b70465ed3cb1e9dc748504ab2a612f54037324068aab1b487189f6d1",
    "videochat3_utils.py": "fd528475338cce9969f43b65df88faf0a72455ab0eeb59cad740733060cef5ab",
}
CERTIFY_RECEIPT_NAME = ".adept-certify.json"


def worker_python() -> Path:
    """GPU interpreter for the isolated worker. Never silently use CPU-only API python."""
    override = (os.environ.get("ADEPT_VIDEO_INTELLIGENCE_PYTHON") or "").strip()
    if override and Path(override).is_file():
        return Path(override)
    home = Path.home()
    candidates = [
        Path(settings.data_dir) / "venvs" / "videochat3-worker" / "Scripts" / "python.exe",
        Path(settings.data_dir) / "venvs" / "videochat3-worker" / "bin" / "python",
        home / "AppData/Local/Comfy-Desktop/ComfyUI-Installs/ComfyUI/standalone-env/python.exe",
        home / "AppData/Local/Comfy-Desktop/ComfyUI-Installs/ComfyUI/ComfyUI/.venv/Scripts/python.exe",
        Path(sys.executable),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return Path(sys.executable)

# Live sibling file list at VIDEOCHAT3_REVISION (HF tree, 2026-08-20). Used when
# list_repo_files is reset by the host network.
VIDEOCHAT3_REPO_FILES = (
    ".gitattributes",
    "README.md",
    "__init__.py",
    "added_tokens.json",
    "chat_template.jinja",
    "chat_template.json",
    "config.json",
    "configuration_videochat3.py",
    "demo_vc3.py",
    "demo_vc3_proactive.py",
    "generation_config.json",
    "inference_fast_vc3.py",
    "merges.txt",
    "model-0001-others-save_rank0.safetensors",
    "model-0002-others-save_rank0.safetensors",
    "model-0003-others-save_rank0.safetensors",
    "model.safetensors.index.json",
    "modeling_videochat3.py",
    "preprocessor_config.json",
    "processing_videochat3.py",
    "processor_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "video_preprocessor_config.json",
    "video_processing_videochat3.py",
    "videochat3_utils.py",
    "vocab.json",
)


def understanding_root() -> Path:
    return Path(settings.data_dir) / "models" / "video_understanding"


def videochat3_dir() -> Path:
    return understanding_root() / "videochat3-4b"


def internvideo3_dir() -> Path:
    return understanding_root() / "internvideo3-8b"


def model_present(root: Path, markers: tuple[str, ...]) -> bool:
    if not root.is_dir():
        return False
    return all((root / name).is_file() for name in markers) and any(root.glob("*.safetensors"))


def _sha256_file(path: Path, *, max_bytes: int | None = None) -> str:
    digest = hashlib.sha256()
    remaining = max_bytes
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            if remaining is not None:
                if remaining <= 0:
                    break
                chunk = chunk[:remaining]
                remaining -= len(chunk)
            digest.update(chunk)
    return digest.hexdigest()


def poll_safe_integrity(root: Path) -> dict[str, Any]:
    """Fast verify: small-file SHA-256 + shard sizes. Does not hash 8.5GB."""
    if not model_present(root, VIDEOCHAT3_MARKERS):
        return {"ok": False, "reason": "NOT_INSTALLED"}
    for name, expected in VIDEOCHAT3_POLL_SHA256.items():
        path = root / name
        if not path.is_file():
            return {"ok": False, "reason": f"MISSING:{name}"}
        actual = _sha256_file(path)
        if actual != expected:
            return {"ok": False, "reason": f"SHA_MISMATCH:{name}", "expected": expected, "actual": actual}
    for name, expected_size in VIDEOCHAT3_WEIGHT_BYTES.items():
        path = root / name
        if not path.is_file():
            return {"ok": False, "reason": f"MISSING:{name}"}
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            return {
                "ok": False,
                "reason": f"SIZE_MISMATCH:{name}",
                "expected": expected_size,
                "actual": actual_size,
            }
    for name, expected in VIDEOCHAT3_REMOTE_CODE_SHA256.items():
        path = root / name
        if not path.is_file():
            return {"ok": False, "reason": f"MISSING:{name}"}
        actual = _sha256_file(path)
        if actual != expected:
            return {"ok": False, "reason": f"SHA_MISMATCH:{name}", "expected": expected, "actual": actual}
    return {"ok": True, "reason": None}


def verify_weight_sha256(root: Path) -> dict[str, Any]:
    """Full shard SHA — install/certify only, never /api/setup/status."""
    checked: dict[str, str] = {}
    for name, expected in VIDEOCHAT3_WEIGHT_SHA256.items():
        path = root / name
        if not path.is_file():
            return {"ok": False, "reason": f"MISSING:{name}", "checked": checked}
        actual = _sha256_file(path)
        checked[name] = actual
        if actual != expected:
            return {"ok": False, "reason": f"SHA_MISMATCH:{name}", "expected": expected, "actual": actual, "checked": checked}
    return {"ok": True, "reason": None, "checked": checked}


def certify_receipt_path(root: Path | None = None) -> Path:
    return (root or videochat3_dir()) / CERTIFY_RECEIPT_NAME
