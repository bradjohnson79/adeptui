from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import settings

ProgressCallback = Callable[[str, float, str, dict[str, Any] | None], None]
CancelCheck = Callable[[], bool]


@dataclass(frozen=True)
class AvatarModelSource:
    repo_id: str
    revision: str
    destination: str
    estimated_bytes: int
    allow_patterns: tuple[str, ...] = ()
    required_markers: tuple[str, ...] = ()
    direct_files: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AvatarRuntimeSpec:
    component_id: str
    provider_id: str
    display_name: str
    creative_role: str
    runtime_slug: str
    description: str
    code_repo: str
    code_revision: str
    code_entrypoint: str
    code_import_probe: str | None
    category: str = "Avatar Runtimes"
    python_version: str = "3.10"
    download_bytes: int = 0
    installed_bytes: int = 0
    required_disk_bytes: int = 0
    min_vram_gb: int | None = None
    recommended_vram_gb: int | None = None
    official_os: tuple[str, ...] = ()
    windows_documented: bool = False
    benchmark_ready: bool = False
    model_sources: tuple[AvatarModelSource, ...] = ()
    extra_pip_packages: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    license_notes: tuple[str, ...] = ()
    listed_as_avatar_generator: bool = False
    supports_speaker_selection: bool = False
    supports_conversation: bool = False
    supports_native_multi_speaker: bool = False
    supports_audio: bool = True
    supports_lora: bool = False
    supported_aspect_ratios: tuple[str, ...] = ("16:9", "9:16", "1:1", "4:5", "3:2", "21:9")
    lora_model_family: str = "video"


MB = 1024 * 1024
GB = 1024 * 1024 * 1024

_RUNTIME_SPECS: tuple[AvatarRuntimeSpec, ...] = (
    AvatarRuntimeSpec(
        component_id="longcat-video-avatar-1-5-local",
        provider_id="longcat-video-avatar-1-5-local",
        display_name="LongCat Avatar 1.5",
        creative_role="Flagship full-body avatar performance",
        runtime_slug="longcat-video-avatar-1-5",
        description=(
            "Experimental flagship avatar runtime for long-form, stylized, and multi-person performance."
        ),
        code_repo="https://github.com/meituan-longcat/LongCat-Video",
        code_revision="6b3f4b8582a8bc3f20f795735f5383716c4ba794",
        code_entrypoint="inference.py",
        code_import_probe="torch",
        python_version="3.10",
        download_bytes=147 * GB,
        installed_bytes=150 * GB,
        required_disk_bytes=170 * GB,
        recommended_vram_gb=48,
        official_os=("linux",),
        windows_documented=False,
        model_sources=(
            AvatarModelSource(
                repo_id="meituan-longcat/LongCat-Video-Avatar-1.5",
                revision="92016c71d5d318d0f5d84e4db30015a571484ab6",
                destination="models/avatar_1_5",
                estimated_bytes=78 * GB,
                required_markers=("README.md",),
            ),
            AvatarModelSource(
                repo_id="meituan-longcat/LongCat-Video",
                revision="03b55529b1d1d4045f5fbe14d65c8c6e8116b278",
                destination="models/longcat_base",
                estimated_bytes=70 * GB,
                required_markers=("README.md",),
            ),
        ),
        extra_pip_packages=(
            "torch==2.6.0",
            "torchvision==0.21.0",
            "torchaudio==2.6.0",
            "flash_attn==2.7.4.post1",
            "librosa",
        ),
        notes=(
            "Official Avatar 1.5 path requires distillation mode.",
            "Official documentation does not publish a numeric VRAM floor.",
        ),
        blockers=(
            "Windows is not documented by the official upstream.",
            "Live deployment-grade VRAM floor still needs real benchmark evidence.",
        ),
        listed_as_avatar_generator=True,
        supports_speaker_selection=False,
        supports_conversation=True,
        supports_native_multi_speaker=False,
        supports_audio=True,
        supports_lora=False,
        lora_model_family="longcat",
    ),
    AvatarRuntimeSpec(
        component_id="infinitetalk-local",
        provider_id="infinitetalk-local",
        display_name="InfiniteTalk",
        creative_role="Secondary long-form streaming avatar",
        runtime_slug="infinitetalk",
        description=(
            "Experimental long-form avatar runtime with streaming, TeaCache, and multi-GPU notes upstream."
        ),
        code_repo="https://github.com/MeiGen-AI/InfiniteTalk",
        code_revision="50aa0a94184315407a991ae804d9b58d6d311ba8",
        code_entrypoint="inference.py",
        code_import_probe="torch",
        python_version="3.10",
        download_bytes=34 * GB,
        installed_bytes=38 * GB,
        required_disk_bytes=44 * GB,
        recommended_vram_gb=32,
        official_os=("linux",),
        windows_documented=False,
        model_sources=(
            AvatarModelSource(
                repo_id="MeiGen-AI/InfiniteTalk",
                revision="d59847ebdacf19245bfca3fb23311c0cada8378a",
                destination="models/infinitetalk",
                estimated_bytes=12 * GB,
                required_markers=("README.md",),
            ),
            AvatarModelSource(
                repo_id="Wan-AI/Wan2.1-I2V-14B-480P",
                revision="6b73f84e66371cdfe870c72acd6826e1d61cf279",
                destination="models/wan_2_1_i2v_14b_480p",
                estimated_bytes=21 * GB,
                required_markers=("README.md",),
            ),
            AvatarModelSource(
                repo_id="TencentGameMate/chinese-wav2vec2-base",
                revision="refs/pr/1",
                destination="models/chinese_wav2vec2_base",
                estimated_bytes=int(1.5 * GB),
                direct_files=(("model.safetensors", "model.safetensors"),),
                required_markers=("model.safetensors",),
            ),
        ),
        extra_pip_packages=(
            "torch==2.4.1",
            "torchvision==0.19.1",
            "torchaudio==2.4.1",
            "xformers==0.0.28",
            "flash_attn==2.7.4.post1",
            "librosa",
        ),
        notes=(
            "Official repo includes a ComfyUI branch, but this installer isolates a direct runtime.",
            "Total storage still needs live confirmation from a full upstream run.",
        ),
        blockers=(
            "Windows is not documented by the official upstream.",
            "Exact total storage and VRAM floor remain upstream unknowns.",
        ),
        listed_as_avatar_generator=True,
        supports_speaker_selection=False,
        supports_conversation=True,
        supports_native_multi_speaker=False,
        supports_audio=True,
        supports_lora=False,
        lora_model_family="wan",
    ),
    AvatarRuntimeSpec(
        component_id="musetalk-1-5-local",
        provider_id="musetalk-1-5-local",
        display_name="MuseTalk 1.5",
        creative_role="Repair and dubbing specialist",
        runtime_slug="musetalk-1-5",
        description=(
            "Experimental repair runtime for lip-sync, dubbing, and avatar reuse with the clearest official Windows story."
        ),
        code_repo="https://github.com/TMElyralab/MuseTalk",
        code_revision="0a89dec45a0192b824e3cf4daf96c239440c5ed8",
        code_entrypoint="scripts/inference.py",
        code_import_probe="torch",
        python_version="3.10",
        download_bytes=10 * GB,
        installed_bytes=12 * GB,
        required_disk_bytes=16 * GB,
        recommended_vram_gb=16,
        official_os=("linux", "win32"),
        windows_documented=True,
        model_sources=(
            AvatarModelSource(
                repo_id="TMElyralab/MuseTalk",
                revision="3ef28bc5cff08c90ad8178a25f1b570cd800170f",
                destination="models/musetalk",
                estimated_bytes=3 * GB,
                allow_patterns=(
                    "models/musetalkV15/unet.pth",
                    "models/musetalkV15/musetalk.json",
                    "README*",
                ),
                required_markers=("models/musetalkV15/unet.pth", "models/musetalkV15/musetalk.json"),
            ),
            AvatarModelSource(
                repo_id="stabilityai/sd-vae-ft-mse",
                revision="main",
                destination="models/sd_vae_ft_mse",
                estimated_bytes=350 * MB,
                required_markers=("README.md",),
            ),
            AvatarModelSource(
                repo_id="yzd-v/DWPose",
                revision="main",
                destination="models/dwpose",
                estimated_bytes=2 * GB,
                required_markers=("README.md",),
            ),
            AvatarModelSource(
                repo_id="openai/whisper-tiny",
                revision="main",
                destination="models/whisper_tiny",
                estimated_bytes=80 * MB,
                required_markers=("README.md",),
            ),
        ),
        extra_pip_packages=(
            "torch==2.0.1",
            "torchvision==0.15.2",
            "torchaudio==2.0.2",
            "mmcv==2.0.1",
            "mmdet==3.1.0",
            "mmpose==1.1.0",
            "mmengine",
            "openmim",
        ),
        blockers=(
            "License review is still required because upstream code and model licensing signals diverge.",
        ),
        license_notes=(
            "Official code and model license signals diverge; treat deployment as blocked pending legal review.",
        ),
    ),
    AvatarRuntimeSpec(
        component_id="echomimic-v2-local",
        provider_id="echomimic-v2-local",
        display_name="EchoMimicV2",
        creative_role="Half-body performance specialist",
        runtime_slug="echomimic-v2",
        description=(
            "Experimental half-body human animation runtime with audio and pose conditioning."
        ),
        code_repo="https://github.com/antgroup/echomimic_v2",
        code_revision="38c86809efa041884c774ee31d984a9577c0e0aa",
        code_entrypoint="inference.py",
        code_import_probe="torch",
        python_version="3.10",
        download_bytes=17 * GB,
        installed_bytes=19 * GB,
        required_disk_bytes=24 * GB,
        recommended_vram_gb=24,
        official_os=("linux",),
        windows_documented=False,
        model_sources=(
            AvatarModelSource(
                repo_id="BadToBest/EchoMimicV2",
                revision="8648078a20057a7cdff6ccd6e91251fe19210533",
                destination="models/echomimic_v2",
                estimated_bytes=15 * GB,
                required_markers=("README.md",),
            ),
            AvatarModelSource(
                repo_id="stabilityai/sd-vae-ft-mse",
                revision="main",
                destination="models/sd_vae_ft_mse",
                estimated_bytes=350 * MB,
                required_markers=("README.md",),
            ),
            AvatarModelSource(
                repo_id="lambdalabs/sd-image-variations-diffusers",
                revision="main",
                destination="models/sd_image_variations",
                estimated_bytes=int(1.5 * GB),
                required_markers=("README.md",),
            ),
            AvatarModelSource(
                repo_id="openai/whisper-tiny",
                revision="main",
                destination="models/whisper_tiny",
                estimated_bytes=80 * MB,
                required_markers=("README.md",),
            ),
        ),
        extra_pip_packages=(
            "torch==2.5.1",
            "torchvision==0.20.1",
            "torchaudio==2.5.1",
            "xformers==0.0.28.post3",
            "torchao",
            "facenet_pytorch==2.6.0",
        ),
        blockers=(
            "Windows is not documented by the official upstream.",
            "Model-license clarity is still incomplete upstream.",
        ),
    ),
)

BY_COMPONENT_ID = {item.component_id: item for item in _RUNTIME_SPECS}
BY_PROVIDER_ID = {item.provider_id: item for item in _RUNTIME_SPECS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_avatar_runtime_component(component_id: str) -> bool:
    return component_id in BY_COMPONENT_ID


def get_spec(component_id: str) -> AvatarRuntimeSpec:
    return BY_COMPONENT_ID[component_id]


def runtime_root(component_id: str) -> Path:
    spec = get_spec(component_id)
    from .model_storage.store import category_root
    return category_root("video") / spec.runtime_slug


def _active_runtime_root(component_id: str) -> Path:
    status = _read_status(component_id)
    configured = str(status.get("runtimeRoot") or "").strip()
    return Path(configured) if configured else runtime_root(component_id)


def code_dir(component_id: str) -> Path:
    return _active_runtime_root(component_id) / "source"


def models_dir(component_id: str) -> Path:
    return _active_runtime_root(component_id) / "models"


def venv_dir(component_id: str) -> Path:
    return _active_runtime_root(component_id) / "venv"


def logs_dir(component_id: str) -> Path:
    return runtime_root(component_id) / "logs"


def log_file(component_id: str) -> Path:
    return logs_dir(component_id) / "install.log"


def status_file(component_id: str) -> Path:
    return runtime_root(component_id) / "adept-runtime.json"


def suggested_install_path(component_id: str) -> str:
    return str(runtime_root(component_id))


def _venv_python(component_id: str) -> Path:
    base = venv_dir(component_id)
    return base / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def _append_log(component_id: str, line: str) -> None:
    target = log_file(component_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(f"[{_now()}] {line.rstrip()}\n")


def _write_status(component_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    root = runtime_root(component_id)
    root.mkdir(parents=True, exist_ok=True)
    current = _read_status(component_id)
    merged = {**current, **payload, "updatedAt": _now()}
    status_file(component_id).write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return merged


def _read_status(component_id: str) -> dict[str, Any]:
    path = status_file(component_id)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _gpu_summary() -> dict[str, Any]:
    info = {
        "available": False,
        "device": None,
        "vramGb": None,
        "cuda": False,
        "message": "PyTorch CUDA not detected from the current API environment.",
    }
    try:
        import torch

        info["cuda"] = bool(torch.cuda.is_available())
        if info["cuda"]:
            props = torch.cuda.get_device_properties(0)
            info["available"] = True
            info["device"] = props.name
            info["vramGb"] = round(float(props.total_memory) / (1024**3), 2)
            info["message"] = f"Detected {props.name} with {info['vramGb']} GB VRAM."
    except Exception as exc:  # noqa: BLE001
        info["message"] = f"GPU preflight unavailable: {exc}"
    return info


def component_metadata(component_id: str) -> dict[str, Any]:
    spec = get_spec(component_id)
    root = runtime_root(component_id)
    status = inspect_runtime(component_id)
    return {
        "purpose": spec.creative_role,
        "min_vram_gb": spec.min_vram_gb,
        "recommended_vram_gb": spec.recommended_vram_gb,
        "source_repo": spec.code_repo,
        "license": "; ".join(spec.license_notes) or "Upstream model / code licenses apply",
        "logs": [str(path) for path in status.get("logPaths") or []],
        "environment": {
            "providerId": spec.provider_id,
            "runtimeRoot": str(root),
            "codeRevision": spec.code_revision,
            "modelRevisions": {
                source.repo_id: source.revision
                for source in spec.model_sources
            },
            "officialOs": list(spec.official_os),
            "windowsDocumented": spec.windows_documented,
            "healthState": status.get("healthState"),
            "benchmarkState": status.get("benchmarkState"),
            "updateAvailable": status.get("updateAvailable"),
            "launchPath": status.get("launchPath"),
            "gpu": status.get("gpu"),
            "notes": list(spec.notes),
            "blockers": list(spec.blockers),
        },
    }


def list_avatar_generator_capabilities() -> list[dict[str, Any]]:
    payload = []
    for spec in _RUNTIME_SPECS:
        payload.append(
            {
                "id": spec.component_id,
                "displayName": spec.display_name,
                "listedAsAvatarGenerator": spec.listed_as_avatar_generator,
                "supportsSpeakerSelection": spec.supports_speaker_selection,
                "supportsConversation": spec.supports_conversation,
                "supportsNativeMultiSpeaker": spec.supports_native_multi_speaker,
                "supportsAudio": spec.supports_audio,
                "supportsLoRA": spec.supports_lora,
                "supportedAspectRatios": list(spec.supported_aspect_ratios),
                "loraModelFamily": spec.lora_model_family,
            }
        )
    return payload


def runtime_gate_line(provider_id: str) -> tuple[bool, str]:
    try:
        runtime = inspect_runtime(provider_id)
    except Exception:
        runtime = {"displayName": provider_id, "healthState": "not_installed", "certifiedReady": False}
    name = str(runtime.get("displayName") or provider_id)
    health = str(runtime.get("healthState") or "not_installed")
    if health == "not_installed":
        return False, f"{name} is not installed. Open Runtime Setup to install it."
    if runtime.get("certifiedReady") is True:
        return True, ""
    return False, f"{name} needs repair — Open Runtime Setup"


def inspect_runtime(component_id: str) -> dict[str, Any]:
    spec = get_spec(component_id)
    status = _read_status(component_id)
    root = Path(str(status.get("runtimeRoot") or runtime_root(component_id)))
    gpu = _gpu_summary()
    code = root / "source"
    models = root / "models"
    venv_python = root / ("venv/Scripts/python.exe" if sys.platform == "win32" else "venv/bin/python")
    launch_path = code / spec.code_entrypoint
    log_paths = [log_file(component_id)] if log_file(component_id).exists() else []

    model_results: list[dict[str, Any]] = []
    all_models_present = True
    for source in spec.model_sources:
        dest = root / source.destination
        missing = []
        for marker in source.required_markers:
            if not (dest / marker).exists():
                missing.append(marker)
        present = dest.exists() and not missing
        model_results.append(
            {
                "repoId": source.repo_id,
                "revision": source.revision,
                "destination": str(dest),
                "present": present,
                "missing": missing,
                "estimatedBytes": source.estimated_bytes,
            }
        )
        if not present:
            all_models_present = False

    code_present = code.exists()
    launch_present = launch_path.exists()
    venv_present = venv_python.exists()
    import_probe_ok = False
    import_probe_message = "Probe not run."
    if venv_present and spec.code_import_probe:
        try:
            completed = subprocess.run(
                [str(venv_python), "-c", f"import {spec.code_import_probe}; print('ok')"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            import_probe_ok = completed.returncode == 0
            import_probe_message = (completed.stdout or completed.stderr or "").strip() or "Import probe completed."
        except Exception as exc:  # noqa: BLE001
            import_probe_message = str(exc)
    else:
        import_probe_ok = venv_present
        import_probe_message = "No import probe configured." if not spec.code_import_probe else "Runtime Python missing."

    update_available = False
    installed_revision = str(status.get("codeRevision") or spec.code_revision)
    if installed_revision and installed_revision != spec.code_revision:
        update_available = True
    for source_result in model_results:
        if str(source_result["revision"]) != str(
            (status.get("modelRevisions") or {}).get(source_result["repoId"], source_result["revision"])
        ):
            update_available = True

    runtime_ready = code_present and venv_present and launch_present and all_models_present and import_probe_ok
    health_state = "experimental" if runtime_ready else ("repair_required" if root.exists() else "not_installed")
    if update_available and runtime_ready:
        health_state = "experimental"
    message = (
        "Pinned runtime files, models, isolated environment, and launch path verified. "
        "Provider remains Experimental until live benchmark coverage is available."
        if runtime_ready
        else "Runtime is incomplete or missing required files."
    )
    if update_available and runtime_ready:
        message = "Runtime works, but one or more pinned revisions differ from the current audited pins."
    return {
        "componentId": component_id,
        "providerId": spec.provider_id,
        "displayName": spec.display_name,
        "runtimeRoot": str(root),
        "codeRoot": str(code),
        "modelsRoot": str(models),
        "venvPython": str(venv_python),
        "launchPath": str(launch_path),
        "logPaths": [str(path) for path in log_paths],
        "installed": root.exists() and (code_present or all_models_present or venv_present),
        "runtimeReady": runtime_ready,
        "healthState": health_state,
        "benchmarkState": "unsupported" if not spec.benchmark_ready else str(status.get("benchmarkState") or "pending"),
        "message": message,
        "codePresent": code_present,
        "venvPresent": venv_present,
        "launchPresent": launch_present,
        "importProbeOk": import_probe_ok,
        "importProbeMessage": import_probe_message,
        "models": model_results,
        "gpu": gpu,
        "codeRevision": installed_revision,
        "pinnedCodeRevision": spec.code_revision,
        "modelRevisions": {item.repo_id: item.revision for item in spec.model_sources},
        "updateAvailable": update_available,
        "blockers": list(spec.blockers),
        "notes": list(spec.notes),
        "officialOs": list(spec.official_os),
        "windowsDocumented": spec.windows_documented,
        "listedAsAvatarGenerator": spec.listed_as_avatar_generator,
        "supportsSpeakerSelection": spec.supports_speaker_selection,
        "supportsConversation": spec.supports_conversation,
        "supportsNativeMultiSpeaker": spec.supports_native_multi_speaker,
        "supportsAudio": spec.supports_audio,
        "supportsLoRA": spec.supports_lora,
        "supportedAspectRatios": list(spec.supported_aspect_ratios),
        "loraModelFamily": spec.lora_model_family,
        "certifiedReady": False,
    }


def verify_runtime(component_id: str) -> dict[str, Any]:
    status = inspect_runtime(component_id)
    return {
        "ok": bool(status.get("runtimeReady")),
        "runtimeReady": bool(status.get("runtimeReady")),
        "healthState": status.get("healthState"),
        "message": str(status.get("message") or ""),
        "inspection": status,
    }


def _run(
    command: list[str],
    *,
    cwd: Path | None,
    component_id: str,
    env: dict[str, str] | None = None,
) -> None:
    _append_log(component_id, f"$ {' '.join(command)}")
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.stdout:
        _append_log(component_id, completed.stdout.strip())
    if completed.stderr:
        _append_log(component_id, completed.stderr.strip())
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}"
        )


def _clone_or_update_repo(component_id: str, repo_url: str, revision: str) -> None:
    target = code_dir(component_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        _run(["git", "clone", repo_url, str(target)], cwd=None, component_id=component_id)
    _run(["git", "fetch", "--all", "--tags"], cwd=target, component_id=component_id)
    _run(["git", "checkout", revision], cwd=target, component_id=component_id)


def _create_venv(component_id: str) -> Path:
    root = venv_dir(component_id)
    if not root.exists():
        _run([sys.executable, "-m", "venv", str(root)], cwd=None, component_id=component_id)
    python = _venv_python(component_id)
    _run([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], cwd=None, component_id=component_id)
    return python


def _install_requirements(component_id: str, spec: AvatarRuntimeSpec, python: Path) -> None:
    repo = code_dir(component_id)
    requirements = repo / "requirements.txt"
    if requirements.exists():
        _run([str(python), "-m", "pip", "install", "-r", str(requirements)], cwd=repo, component_id=component_id)
    if spec.extra_pip_packages:
        _run([str(python), "-m", "pip", "install", *spec.extra_pip_packages], cwd=repo, component_id=component_id)


def _download_models(
    component_id: str,
    spec: AvatarRuntimeSpec,
    *,
    emit: ProgressCallback,
    cancel_check: CancelCheck | None,
) -> list[dict[str, Any]]:
    try:
        from huggingface_hub import hf_hub_download, snapshot_download
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError("huggingface_hub is required for avatar runtime downloads.") from exc

    total = sum(item.estimated_bytes for item in spec.model_sources)
    complete = 0
    downloaded: list[dict[str, Any]] = []
    for index, source in enumerate(spec.model_sources, start=1):
        if cancel_check and cancel_check():
            raise RuntimeError("Install cancelled.")
        current = f"{source.repo_id}@{source.revision}"
        emit(
            "downloading",
            complete / total if total else 0.0,
            f"Downloading {current}",
            {"currentFile": current, "stepIndex": index, "stepCount": len(spec.model_sources)},
        )
        destination = runtime_root(component_id) / source.destination
        destination.mkdir(parents=True, exist_ok=True)
        if source.direct_files:
            for remote_name, local_name in source.direct_files:
                hf_hub_download(
                    repo_id=source.repo_id,
                    revision=source.revision,
                    filename=remote_name,
                    local_dir=str(destination),
                    local_dir_use_symlinks=False,
                )
                if remote_name != local_name and (destination / remote_name).exists():
                    shutil.move(str(destination / remote_name), str(destination / local_name))
        else:
            kwargs: dict[str, Any] = {
                "repo_id": source.repo_id,
                "revision": source.revision,
                "local_dir": str(destination),
                "local_dir_use_symlinks": False,
            }
            if source.allow_patterns:
                kwargs["allow_patterns"] = list(source.allow_patterns)
            snapshot_download(**kwargs)
        complete += source.estimated_bytes
        downloaded.append(
            {
                "repoId": source.repo_id,
                "revision": source.revision,
                "destination": str(destination),
                "estimatedBytes": source.estimated_bytes,
            }
        )
        emit(
            "downloading",
            complete / total if total else 1.0,
            f"Downloaded {current}",
            {"currentFile": current, "stepIndex": index, "stepCount": len(spec.model_sources)},
        )
    return downloaded


def install_runtime(
    component_id: str,
    *,
    destination: str | None,
    confirm_download_models: bool,
    source_url: str | None = None,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
    force: bool = False,
) -> dict[str, Any]:
    spec = get_spec(component_id)
    if not confirm_download_models:
        return {
            "ok": False,
            "message": "Explicit model-download confirmation is required for avatar runtimes.",
            "error": {"code": "confirm_required", "message": "confirmDownloadModels must be true."},
        }

    root = Path(destination or runtime_root(component_id))
    root.mkdir(parents=True, exist_ok=True)
    code_repo = source_url if source_url and "github.com" in source_url else spec.code_repo

    def emit(phase: str, frac: float, message: str, details: dict[str, Any] | None = None) -> None:
        payload = details or {}
        _append_log(component_id, f"{phase}: {message}")
        if progress_callback:
            progress_callback(phase, frac, message, payload)

    platform_name = sys.platform
    warnings = []
    if spec.official_os and platform_name not in spec.official_os:
        warnings.append(
            f"{spec.display_name} is only officially documented for {', '.join(spec.official_os)}."
        )
    if platform_name == "win32" and not spec.windows_documented:
        warnings.append("Windows support is not documented by the official upstream.")
    gpu = _gpu_summary()
    if spec.recommended_vram_gb and gpu.get("vramGb") is not None and gpu["vramGb"] < spec.recommended_vram_gb:
        warnings.append(
            f"Detected {gpu['vramGb']} GB VRAM, below the recommended {spec.recommended_vram_gb} GB."
        )

    _write_status(
        component_id,
        {
            "componentId": component_id,
            "providerId": spec.provider_id,
            "runtimeRoot": str(root),
            "managed": True,
            "installState": "installing",
            "healthState": "verifying",
            "codeRepo": code_repo,
            "codeRevision": spec.code_revision,
            "modelRevisions": {item.repo_id: item.revision for item in spec.model_sources},
            "warnings": warnings,
            "gpu": gpu,
            "confirmedModelDownload": confirm_download_models,
            "sourceOverride": source_url,
            "logPaths": [str(log_file(component_id))],
        },
    )

    try:
        emit("preflight", 0.02, "Preparing isolated avatar runtime.", {"currentFile": None})
        _append_log(component_id, f"force={force} destination={root}")
        for warning in warnings:
            _append_log(component_id, f"warning: {warning}")

        emit("preparing", 0.08, "Cloning pinned source repository.", {"currentFile": code_repo})
        _clone_or_update_repo(component_id, code_repo, spec.code_revision)

        emit("installing", 0.18, "Creating isolated Python environment.", {"currentFile": "venv"})
        python = _create_venv(component_id)

        emit("installing", 0.28, "Installing pinned runtime dependencies.", {"currentFile": "pip"})
        _install_requirements(component_id, spec, python)

        models = _download_models(
            component_id,
            spec,
            emit=emit,
            cancel_check=cancel_check,
        )

        emit("verifying_install", 0.92, "Verifying runtime files, pins, and launch path.", {"currentFile": spec.code_entrypoint})
        inspection = inspect_runtime(component_id)
        if not inspection.get("runtimeReady"):
            raise RuntimeError(inspection.get("message") or "Runtime verification failed.")

        benchmark_state = "pending" if spec.benchmark_ready else "not_available"
        message = (
            f"{spec.display_name} installed at pinned revisions. Status remains Experimental until live benchmarks are available."
        )
        status = _write_status(
            component_id,
            {
                "installState": "installed",
                "healthState": "experimental",
                "benchmarkState": benchmark_state,
                "launchPath": inspection.get("launchPath"),
                "venvPython": str(python),
                "warnings": warnings,
                "models": models,
                "completedAt": _now(),
            },
        )
        emit("completed", 1.0, message, {"currentFile": None})
        return {
            "ok": True,
            "runtimeReady": True,
            "state": "ready",
            "message": message,
            "healthState": "experimental",
            "inspection": inspection,
            "status": status,
            "logPaths": [str(log_file(component_id))],
        }
    except Exception as exc:  # noqa: BLE001
        _append_log(component_id, f"error: {exc}")
        status = _write_status(
            component_id,
            {
                "installState": "repair_required",
                "healthState": "repair_required",
                "lastError": str(exc),
                "failedAt": _now(),
            },
        )
        return {
            "ok": False,
            "message": str(exc),
            "error": {"code": "avatar_runtime_install_failed", "message": str(exc)},
            "status": status,
            "logPaths": [str(log_file(component_id))],
        }


def link_existing_runtime(component_id: str, path: str) -> dict[str, Any]:
    spec = get_spec(component_id)
    root = Path(path).expanduser()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Existing runtime folder not found: {path}")
    _write_status(
        component_id,
        {
            "componentId": component_id,
            "providerId": spec.provider_id,
            "runtimeRoot": str(root),
            "managed": False,
            "installState": "linked",
            "healthState": "verifying",
            "codeRepo": spec.code_repo,
            "codeRevision": spec.code_revision,
            "modelRevisions": {item.repo_id: item.revision for item in spec.model_sources},
            "logPaths": [str(log_file(component_id))],
        },
    )
    inspection = inspect_runtime(component_id)
    if not inspection.get("runtimeReady"):
        raise ValueError(inspection.get("message") or "Linked runtime failed verification.")
    status = _write_status(
        component_id,
        {
            "managed": False,
            "installState": "linked",
            "healthState": "experimental",
            "benchmarkState": "not_available" if not spec.benchmark_ready else "pending",
            "launchPath": inspection.get("launchPath"),
        },
    )
    return {
        "ok": True,
        "message": (
            f"Linked existing {spec.display_name} runtime. Status remains Experimental until live benchmark coverage exists."
        ),
        "inspection": inspection,
        "status": status,
    }


def remove_runtime(component_id: str) -> dict[str, Any]:
    status = _read_status(component_id)
    root = Path(str(status.get("runtimeRoot") or runtime_root(component_id)))
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    meta = runtime_root(component_id)
    if meta.exists() and meta != root:
        shutil.rmtree(meta, ignore_errors=True)
    return {
        "ok": True,
        "removed": True,
        "path": str(root),
        "message": f"Removed {get_spec(component_id).display_name} runtime files.",
    }


def benchmark_runtime(component_id: str) -> dict[str, Any]:
    spec = get_spec(component_id)
    inspection = inspect_runtime(component_id)
    target = logs_dir(component_id) / "benchmark.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "componentId": component_id,
        "providerId": spec.provider_id,
        "requestedAt": _now(),
        "runtimeReady": inspection.get("runtimeReady"),
        "status": "not_available" if not spec.benchmark_ready else "pending",
        "message": (
            "Benchmark hook recorded. Live avatar benchmark suite is not available yet."
            if not spec.benchmark_ready
            else "Benchmark hook recorded."
        ),
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_status(component_id, {"benchmarkState": payload["status"]})
    return {
        "ok": True,
        "status": payload["status"],
        "message": payload["message"],
        "reportPath": str(target),
    }


def preflight(component_id: str, *, destination: str | None = None) -> dict[str, Any]:
    spec = get_spec(component_id)
    root = Path(destination or runtime_root(component_id))
    probe = root if root.exists() else root.parent
    disk_free = None
    disk_ok = None
    try:
        disk_free = shutil.disk_usage(str(probe)).free
        disk_ok = disk_free >= spec.required_disk_bytes
    except OSError:
        disk_free = None
    gpu = _gpu_summary()
    return {
        "componentId": component_id,
        "providerId": spec.provider_id,
        "destination": str(root),
        "officialSource": {
            "codeRepo": spec.code_repo,
            "codeRevision": spec.code_revision,
            "modelRepos": [
                {"repoId": item.repo_id, "revision": item.revision}
                for item in spec.model_sources
            ],
        },
        "downloadBytes": spec.download_bytes,
        "requiredDiskBytes": spec.required_disk_bytes,
        "availableDiskBytes": disk_free,
        "hasEnoughDisk": disk_ok,
        "gpu": gpu,
        "windowsDocumented": spec.windows_documented,
        "officialOs": list(spec.official_os),
        "blockers": list(spec.blockers),
        "notes": list(spec.notes),
    }


def catalog_entry(component_id: str) -> dict[str, Any]:
    spec = get_spec(component_id)
    return {
        "providerId": spec.provider_id,
        "displayName": spec.display_name,
        "creativeRole": spec.creative_role,
        "runtimeSlug": spec.runtime_slug,
        "description": spec.description,
        "downloadBytes": spec.download_bytes,
        "installedBytes": spec.installed_bytes,
        "requiredDiskBytes": spec.required_disk_bytes,
        "pythonVersion": spec.python_version,
        "codeRepo": spec.code_repo,
        "codeRevision": spec.code_revision,
        "models": [asdict(item) for item in spec.model_sources],
        "notes": list(spec.notes),
        "blockers": list(spec.blockers),
    }
