"""MAGI GPU Upscaling runtime — Real-ESRGAN-ncnn-Vulkan via Setup.

Installs the pinned official Windows portable zip into
``settings.data_dir / runtimes / realesrgan-ncnn-vulkan``.
Ready requires binary + models + launch + Vulkan inference probe.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from ..config import settings

COMPONENT_ID = "magi_gpu_upscale"
RUNTIME_SLUG = "realesrgan-ncnn-vulkan"
ENGINE_ID = "realesrgan-ncnn-vulkan"

ENGINE_REPO = "https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan"
ENGINE_LICENSE = "MIT"
MODEL_REPO = "https://github.com/xinntao/Real-ESRGAN"
MODEL_LICENSE = "BSD-3-Clause"

PINNED_VERSION = "v0.2.5.0-20220424"
PINNED_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
    "realesrgan-ncnn-vulkan-20220424-windows.zip"
)
PINNED_FILENAME = "realesrgan-ncnn-vulkan-20220424-windows.zip"
PINNED_SHA256 = "ABC02804E17982A3BE33675E4D471E91EA374E65B70167ABC09E31ACB412802D"
PINNED_BYTES = 45474481

REQUIRED_MODELS = (
    "realesr-animevideov3-x2",
    "realesr-animevideov3-x3",
    "realesr-animevideov3-x4",
    "realesrgan-x4plus",
    "realesrgan-x4plus-anime",
)

CREATOR_UNAVAILABLE = "GPU Upscaling unavailable. FFmpeg upscale remains available."

_ATTRIBUTION = """MAGI GPU Upscaling uses Real-ESRGAN-ncnn-Vulkan.

Engine: https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan
License: MIT Copyright (c) 2021 Xintao Wang
         MIT Copyright (c) 2019 nihui (realsr-ncnn-vulkan)

Models: https://github.com/xinntao/Real-ESRGAN
License: BSD 3-Clause Copyright (c) 2021, Xintao Wang

The pinned Windows portable package is downloaded on install and is not
redistributed inside the Adept UI source tree.
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def runtime_root() -> Path:
    return Path(settings.data_dir) / "runtimes" / RUNTIME_SLUG


def cache_dir() -> Path:
    return Path(settings.data_dir) / "runtimes" / "_cache"


def binary_path() -> Path:
    root = runtime_root()
    if os_name_windows():
        return root / "realesrgan-ncnn-vulkan.exe"
    return root / "realesrgan-ncnn-vulkan"


def models_dir() -> Path:
    return runtime_root() / "models"


def manifest_path() -> Path:
    return runtime_root() / "manifest.json"


def os_name_windows() -> bool:
    import os

    return os.name == "nt"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _model_pair_exists(name: str) -> bool:
    folder = models_dir()
    return (folder / f"{name}.bin").is_file() and (folder / f"{name}.param").is_file()


def files_present() -> bool:
    exe = binary_path()
    if not exe.is_file():
        return False
    return all(_model_pair_exists(name) for name in REQUIRED_MODELS)


def _run(cmd: list[str], *, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def binary_launches() -> tuple[bool, str]:
    exe = binary_path()
    if not exe.is_file():
        return False, "binary_missing"
    try:
        proc = _run([str(exe), "-h"], timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)[:240]
    text = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    if "Usage:" in text or "realesrgan" in text.lower() or proc.returncode in (0, 1):
        return True, text[:400]
    return False, text[:400] or f"exit {proc.returncode}"


def _write_probe_png(path: Path) -> None:
    # Valid 1x1 RGB PNG so the probe does not depend on demo assets.
    path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
            "0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e44ae426082"
        )
    )


def inference_probe() -> dict[str, Any]:
    exe = binary_path()
    models = models_dir()
    if not exe.is_file() or not models.is_dir():
        return {"ok": False, "reason": "files_missing"}
    work = Path(tempfile.mkdtemp(prefix="realesrgan_probe_"))
    try:
        src = work / "in.png"
        dest = work / "out.png"
        _write_probe_png(src)
        cmd = [
            str(exe),
            "-i",
            str(src),
            "-o",
            str(dest),
            "-n",
            "realesr-animevideov3",
            "-s",
            "2",
            "-m",
            str(models),
        ]
        try:
            proc = _run(cmd, timeout=90)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "reason": "probe_exec_failed", "detail": str(exc)[:240]}
        text = f"{proc.stdout or ''}\n{proc.stderr or ''}"
        vulkan_ok = "failed" not in text.lower() or dest.is_file()
        if proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0:
            gpu = ""
            for line in text.splitlines():
                if "gpu" in line.lower() or "device" in line.lower():
                    gpu = line.strip()
                    break
            return {
                "ok": True,
                "vulkan": True,
                "device": gpu or "vulkan-auto",
                "outputBytes": dest.stat().st_size,
            }
        lowered = text.lower()
        if "vulkan" in lowered and ("error" in lowered or "failed" in lowered or "not found" in lowered):
            return {"ok": False, "reason": "vulkan_unavailable", "detail": text[:400], "vulkan": False}
        if not vulkan_ok:
            return {"ok": False, "reason": "vulkan_unavailable", "detail": text[:400], "vulkan": False}
        return {"ok": False, "reason": "probe_failed", "detail": text[:400], "vulkan": dest.is_file()}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def inspect_installation() -> dict[str, Any]:
    root = runtime_root()
    exe = binary_path()
    models = models_dir()
    manifest = _read_json(manifest_path())
    present = files_present()
    launches = False
    launch_detail = ""
    if present:
        launches, launch_detail = binary_launches()
    probe = manifest.get("lastProbe") if isinstance(manifest.get("lastProbe"), dict) else {}
    ready = bool(present and launches and probe.get("ok"))
    return {
        "componentId": COMPONENT_ID,
        "engineId": ENGINE_ID,
        "supportedInCode": True,
        "realesrganReady": ready,
        "filesPresent": present,
        "binaryExists": exe.is_file(),
        "binaryLaunches": launches,
        "modelsExist": all(_model_pair_exists(name) for name in REQUIRED_MODELS),
        "vulkanDeviceAvailable": bool(probe.get("ok") or probe.get("vulkan")),
        "inferenceProbePassed": bool(probe.get("ok")),
        "creatorMessage": None if ready else CREATOR_UNAVAILABLE,
        "paths": {
            "installPath": str(root),
            "binaryPath": str(exe),
            "modelPath": str(models),
        },
        "version": manifest.get("version") or PINNED_VERSION,
        "hash": manifest.get("hash"),
        "installedAt": manifest.get("installedAt"),
        "verifiedAt": manifest.get("verifiedAt"),
        "launchDetail": launch_detail[:200],
        "lastProbe": probe,
        "licenses": {
            "engine": ENGINE_LICENSE,
            "engineRepo": ENGINE_REPO,
            "models": MODEL_LICENSE,
            "modelRepo": MODEL_REPO,
        },
    }


def readiness() -> dict[str, Any]:
    inspection = inspect_installation()
    return {
        "supportedInCode": True,
        "realesrganReady": bool(inspection.get("realesrganReady")),
        "available": bool(inspection.get("realesrganReady")),
        "creatorMessage": inspection.get("creatorMessage"),
        "binaryPath": inspection["paths"]["binaryPath"],
        "modelPath": inspection["paths"]["modelPath"],
        "version": inspection.get("version"),
        "vulkanDeviceAvailable": inspection.get("vulkanDeviceAvailable"),
        "inferenceProbePassed": inspection.get("inferenceProbePassed"),
        "device": (inspection.get("lastProbe") or {}).get("device"),
    }


def _download_zip(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size == PINNED_BYTES:
        if _sha256_file(dest) == PINNED_SHA256:
            return dest
        dest.unlink(missing_ok=True)
    req = Request(PINNED_URL, headers={"User-Agent": "AdeptUI-MAGI-Setup/1.0"})
    with urlopen(req, timeout=120) as response, dest.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    if dest.stat().st_size != PINNED_BYTES:
        raise RuntimeError(f"Downloaded size {dest.stat().st_size} != pinned {PINNED_BYTES}")
    digest = _sha256_file(dest)
    if digest != PINNED_SHA256:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 mismatch: {digest} != {PINNED_SHA256}")
    return dest


def _extract_install(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="realesrgan_extract_") as tmp:
        work = Path(tmp) / "unpack"
        work.mkdir()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(work)
        root = work
        nested = [p for p in work.iterdir() if p.is_dir()]
        if not (work / "realesrgan-ncnn-vulkan.exe").is_file() and len(nested) == 1:
            root = nested[0]
        for name in ("realesrgan-ncnn-vulkan.exe", "vcomp140.dll", "vcomp140d.dll", "README_windows.md"):
            src = root / name
            if src.is_file():
                shutil.copy2(src, dest / name)
        models_src = root / "models"
        models_dest = dest / "models"
        if models_src.is_dir():
            if models_dest.exists():
                shutil.rmtree(models_dest)
            shutil.copytree(models_src, models_dest)
    (dest / "NOTICE.txt").write_text(_ATTRIBUTION, encoding="utf-8")


def install(*, force: bool = False) -> dict[str, Any]:
    existing = inspect_installation()
    if existing.get("realesrganReady") and not force:
        return {
            "ok": True,
            "reused": True,
            "message": "MAGI GPU Upscaling is already installed and ready.",
            "runtime": existing,
        }
    if files_present() and not force:
        probe = inference_probe()
        launches, _ = binary_launches()
        manifest = {
            **_read_json(manifest_path()),
            "version": PINNED_VERSION,
            "installPath": str(runtime_root()),
            "binaryPath": str(binary_path()),
            "modelPath": str(models_dir()),
            "hash": PINNED_SHA256,
            "installedAt": _read_json(manifest_path()).get("installedAt") or _now(),
            "verifiedAt": _now(),
            "lastProbe": probe,
            "reused": True,
        }
        _write_json(manifest_path(), manifest)
        ready = bool(launches and probe.get("ok"))
        return {
            "ok": ready,
            "reused": True,
            "realesrganReady": ready,
            "message": "Verified existing MAGI GPU Upscaling install." if ready else CREATOR_UNAVAILABLE,
            "runtime": inspect_installation(),
        }

    zip_path = cache_dir() / PINNED_FILENAME
    try:
        _download_zip(zip_path)
        dest = runtime_root()
        dest.mkdir(parents=True, exist_ok=True)
        _extract_install(zip_path, dest)
        launches, launch_detail = binary_launches()
        probe = inference_probe() if launches else {"ok": False, "reason": "binary_unusable", "detail": launch_detail}
        manifest = {
            "componentId": COMPONENT_ID,
            "version": PINNED_VERSION,
            "sourceUrl": PINNED_URL,
            "installPath": str(dest),
            "binaryPath": str(binary_path()),
            "modelPath": str(models_dir()),
            "hash": PINNED_SHA256,
            "installedAt": _now(),
            "verifiedAt": _now(),
            "lastProbe": probe,
            "licenses": {
                "engine": ENGINE_LICENSE,
                "engineRepo": ENGINE_REPO,
                "models": MODEL_LICENSE,
                "modelRepo": MODEL_REPO,
            },
        }
        _write_json(manifest_path(), manifest)
        ready = bool(launches and probe.get("ok"))
        return {
            "ok": True,
            "reused": False,
            "realesrganReady": ready,
            "message": (
                "MAGI GPU Upscaling installed and verified."
                if ready
                else f"Installed files, but not Ready. {CREATOR_UNAVAILABLE}"
            ),
            "runtime": inspect_installation(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "reused": False,
            "realesrganReady": False,
            "error": {"code": "realesrgan_install_failed", "message": str(exc)[:500]},
            "message": f"MAGI GPU Upscaling install failed: {exc}"[:400],
        }


def verify(*, repair: bool = False) -> dict[str, Any]:
    if repair and not files_present():
        return install(force=True)
    if not files_present():
        return {"ok": False, "realesrganReady": False, "message": CREATOR_UNAVAILABLE}
    launches, _ = binary_launches()
    probe = inference_probe()
    manifest = {
        **_read_json(manifest_path()),
        "version": PINNED_VERSION,
        "installPath": str(runtime_root()),
        "binaryPath": str(binary_path()),
        "modelPath": str(models_dir()),
        "hash": PINNED_SHA256,
        "verifiedAt": _now(),
        "lastProbe": probe,
    }
    if not manifest.get("installedAt"):
        manifest["installedAt"] = _now()
    _write_json(manifest_path(), manifest)
    ready = bool(launches and probe.get("ok"))
    return {
        "ok": ready,
        "realesrganReady": ready,
        "message": "MAGI GPU Upscaling verified." if ready else CREATOR_UNAVAILABLE,
        "runtime": inspect_installation(),
    }


def resolve_model(model: str, scale: int | None = None) -> tuple[str, int]:
    """Map creator model ids onto official ncnn -n names and -s scale."""
    name = (model or "").strip().lower()
    if name in {"realesr-animevideov3", "anime", "anime-video", "anime_video"}:
        chosen_scale = scale if scale in (2, 3, 4) else 4
        return "realesr-animevideov3", chosen_scale
    if name in {"realesrgan-x4plus-anime", "anime-4x", "anime_4x"}:
        return "realesrgan-x4plus-anime", 4
    if name in {"realesrgan-x4plus", "general", "general-4x", "x4plus"}:
        return "realesrgan-x4plus", 4
    if "anime" in name:
        return "realesr-animevideov3", scale if scale in (2, 3, 4) else 4
    return "realesrgan-x4plus", 4
