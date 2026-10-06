"""Canonical Adept Runtime config — %APPDATA%\\Adept\\Runtime\\runtime.json.

Worktree .venv and Desktop Comfy are discovery hints only.
Production authority is this file. No hardcoded user or D:\\01_Models paths.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .constants import API_PORT, CONTROL_PORT, COMFY_PORT, RETIRED_WEB_PORT, RUNTIME_VERSION


class ConfigurationError(ValueError):
    """Invalid or missing runtime.json. Do not spawn or register a task."""


@dataclass
class RecoverySettings:
    maxRestarts: int = 5
    baseBackoffSec: int = 5
    maxBackoffSec: int = 120


@dataclass
class StudioApiSettings:
    enabled: bool = True
    python: str = ""
    appRoot: str = ""
    port: int = API_PORT


@dataclass
class RuntimeConfig:
    comfyRoot: str
    comfyPython: str
    modelRoot: str
    port: int = COMFY_PORT
    logDir: str = ""
    runtimeVersion: str = RUNTIME_VERSION
    recovery: RecoverySettings = field(default_factory=RecoverySettings)
    controlPort: int = CONTROL_PORT
    stateDir: str = ""
    servicePython: str = ""
    modelFolders: dict[str, str] = field(default_factory=dict)
    repoRoot: str = ""
    autostart: bool = True
    studioApi: StudioApiSettings = field(default_factory=StudioApiSettings)

    def comfy_root_path(self) -> Path:
        return Path(self.comfyRoot)

    def comfy_python_path(self) -> Path:
        return Path(self.comfyPython)

    def model_root_path(self) -> Path:
        return Path(self.modelRoot)

    def log_dir_path(self) -> Path:
        return Path(self.logDir)

    def state_dir_path(self) -> Path:
        return Path(self.stateDir)

    def service_python_path(self) -> Path:
        raw = (self.servicePython or self.comfyPython or "").strip()
        return Path(raw) if raw else Path()

    def folder(self, name: str) -> Path | None:
        raw = str(self.modelFolders.get(name) or "").strip()
        if raw:
            return Path(raw)
        if name and self.modelRoot:
            candidate = self.model_root_path() / name
            return candidate if candidate.is_dir() else None
        return None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["recovery"] = asdict(self.recovery)
        data["studioApi"] = asdict(self.studioApi)
        return data


def appdata_dir() -> Path:
    override = (os.environ.get("ADEPT_RUNTIME_HOME") or "").strip()
    if override:
        return Path(override)
    appdata = (os.environ.get("APPDATA") or "").strip()
    if not appdata:
        raise ConfigurationError("APPDATA is not set; cannot place Adept Runtime config.")
    return Path(appdata) / "Adept" / "Runtime"


def localappdata_dir() -> Path:
    override = (os.environ.get("ADEPT_RUNTIME_STATE_HOME") or "").strip()
    if override:
        return Path(override)
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return Path(local) / "Adept" / "Runtime"
    return appdata_dir()


def config_path() -> Path:
    override = (os.environ.get("ADEPT_RUNTIME_CONFIG") or "").strip()
    if override:
        return Path(override)
    return appdata_dir() / "runtime.json"


def default_log_dir() -> Path:
    return localappdata_dir() / "logs"


def default_state_dir() -> Path:
    return localappdata_dir() / "supervisor"


def _recovery_from(raw: Any) -> RecoverySettings:
    if not isinstance(raw, dict):
        return RecoverySettings()
    return RecoverySettings(
        maxRestarts=int(raw.get("maxRestarts") or 5),
        baseBackoffSec=int(raw.get("baseBackoffSec") or 5),
        maxBackoffSec=int(raw.get("maxBackoffSec") or 120),
    )


def _studio_api_from(raw: Any) -> StudioApiSettings:
    if not isinstance(raw, dict):
        return StudioApiSettings()
    enabled = raw.get("enabled")
    return StudioApiSettings(
        enabled=True if enabled is None else bool(enabled),
        python=str(raw.get("python") or "").strip(),
        appRoot=str(raw.get("appRoot") or "").strip(),
        port=int(raw.get("port") or API_PORT),
    )


def parse_runtime_config(data: dict[str, Any]) -> RuntimeConfig:
    folders = data.get("modelFolders") if isinstance(data.get("modelFolders"), dict) else {}
    return RuntimeConfig(
        comfyRoot=str(data.get("comfyRoot") or "").strip(),
        comfyPython=str(data.get("comfyPython") or "").strip(),
        modelRoot=str(data.get("modelRoot") or "").strip(),
        port=int(data.get("port") or COMFY_PORT),
        logDir=str(data.get("logDir") or default_log_dir()),
        runtimeVersion=str(data.get("runtimeVersion") or RUNTIME_VERSION),
        recovery=_recovery_from(data.get("recovery")),
        controlPort=int(data.get("controlPort") or CONTROL_PORT),
        stateDir=str(data.get("stateDir") or default_state_dir()),
        servicePython=str(data.get("servicePython") or "").strip(),
        modelFolders={str(k): str(v) for k, v in folders.items() if str(v).strip()},
        repoRoot=str(data.get("repoRoot") or "").strip(),
        autostart=bool(data["autostart"]) if "autostart" in data else True,
        studioApi=_studio_api_from(data.get("studioApi")),
    )


def load_runtime_config() -> RuntimeConfig:
    path = config_path()
    if not path.is_file():
        raise ConfigurationError(f"CONFIGURATION ERROR: runtime.json missing at {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"CONFIGURATION ERROR: runtime.json unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("CONFIGURATION ERROR: runtime.json must be an object")
    return parse_runtime_config(raw)


def try_load_runtime_config() -> RuntimeConfig | None:
    try:
        return load_runtime_config()
    except ConfigurationError:
        return None


def validate_runtime_config(cfg: RuntimeConfig) -> list[str]:
    errors: list[str] = []
    # Empty Comfy paths mean the picture engine is not set up yet. Background
    # Services still starts and reports that state. A path that is set must be real.
    comfy_root = (cfg.comfyRoot or "").strip()
    comfy_python = (cfg.comfyPython or "").strip()
    if comfy_root or comfy_python:
        if not comfy_root:
            errors.append("comfyRoot is required")
        else:
            root = cfg.comfy_root_path()
            main = root / "ComfyUI" / "main.py"
            if not main.is_file():
                main = root / "main.py"
            if not root.is_dir():
                errors.append(f"comfyRoot is not a directory: {root}")
            elif not main.is_file():
                errors.append(f"Comfy main.py missing under {root}")
        if not comfy_python:
            errors.append("comfyPython is required")
        elif not cfg.comfy_python_path().is_file():
            errors.append(f"comfyPython is not a file: {cfg.comfyPython}")
    if cfg.port != COMFY_PORT:
        errors.append(f"port must be {COMFY_PORT} for canonical Adept Comfy")
    if int(cfg.controlPort) == RETIRED_WEB_PORT:
        errors.append(f"controlPort must not be retired :{RETIRED_WEB_PORT}")
    if int(cfg.controlPort) <= 0 or int(cfg.controlPort) > 65535:
        errors.append("controlPort is invalid")
    if not cfg.modelRoot:
        errors.append("modelRoot is required")
    elif not cfg.model_root_path().is_dir():
        errors.append(f"modelRoot is not a directory: {cfg.modelRoot}")
    if cfg.studioApi.port and int(cfg.studioApi.port) != API_PORT:
        errors.append(f"studioApi.port must be {API_PORT}")
    if cfg.studioApi.enabled:
        if cfg.studioApi.python and not Path(cfg.studioApi.python).is_file():
            errors.append(f"studioApi.python is not a file: {cfg.studioApi.python}")
        if cfg.studioApi.appRoot and not Path(cfg.studioApi.appRoot).is_dir():
            errors.append(f"studioApi.appRoot is not a directory: {cfg.studioApi.appRoot}")
    return errors


def write_runtime_config(cfg: RuntimeConfig) -> Path:
    errors = validate_runtime_config(cfg)
    if errors:
        raise ConfigurationError("CONFIGURATION ERROR: " + "; ".join(errors))
    dest = config_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    Path(cfg.logDir).mkdir(parents=True, exist_ok=True)
    Path(cfg.stateDir).mkdir(parents=True, exist_ok=True)
    payload = cfg.to_dict()
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(dest)
    return dest


def _first_file(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def _first_dir(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_dir():
            return path
    return None


def discover_comfy_hint() -> tuple[Path | None, Path | None]:
    env_root = (os.environ.get("ADEPT_COMFY_ROOT") or "").strip()
    env_py = (os.environ.get("ADEPT_COMFY_PYTHON") or "").strip()
    if env_root:
        root = Path(env_root)
        py = Path(env_py) if env_py else _first_file(
            root / "ComfyUI" / ".venv" / "Scripts" / "python.exe",
            root / ".venv" / "Scripts" / "python.exe",
            root / "python.exe",
        )
        if root.is_dir() and py is not None:
            return root, py
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    desktop = Path(local) / "Comfy-Desktop" / "ComfyUI-Installs" if local else None
    if desktop and desktop.is_dir():
        for install in sorted(desktop.iterdir()):
            main = install / "ComfyUI" / "main.py"
            py = install / "ComfyUI" / ".venv" / "Scripts" / "python.exe"
            if main.is_file() and py.is_file():
                return install, py
    return None, None


def _folders_from_existing_yaml() -> dict[str, Path]:
    """Migrate model folders from the Adept-owned extra_model_paths.yaml if present."""
    appdata = (os.environ.get("APPDATA") or "").strip()
    if not appdata:
        return {}
    yaml = Path(appdata) / "Adept" / "Comfy" / "extra_model_paths.yaml"
    if not yaml.is_file():
        return {}
    found: dict[str, Path] = {}
    current = ""
    for line in yaml.read_text(encoding="utf-8").splitlines():
        raw = line.rstrip()
        if raw and not raw.startswith(" ") and raw.endswith(":"):
            current = raw[:-1].strip()
            continue
        if current and "base_path:" in raw:
            value = raw.split("base_path:", 1)[1].strip()
            path = Path(value)
            if path.is_dir():
                found[current] = path
    return found


def discover_model_root_hint() -> Path | None:
    env_root = (os.environ.get("ADEPT_MODEL_ROOT") or "").strip()
    if env_root and Path(env_root).is_dir():
        return Path(env_root)
    existing = try_load_runtime_config()
    if existing and existing.modelRoot and Path(existing.modelRoot).is_dir():
        return Path(existing.modelRoot)
    yaml_folders = _folders_from_existing_yaml()
    qwen = yaml_folders.get("adept_qwen_edit_2509")
    if qwen is not None:
        parent = qwen
        for _ in range(3):
            if parent.name.lower() in {"qwen", "comfyui"}:
                parent = parent.parent
                continue
            if parent.is_dir():
                return parent
            break
    return None


def discover_service_python_hint(repo_root: Path | None = None) -> Path | None:
    env_py = (os.environ.get("ADEPT_RUNTIME_PYTHON") or "").strip()
    if env_py and Path(env_py).is_file():
        return Path(env_py)
    if repo_root:
        win = repo_root / "studio-api" / ".venv" / "Scripts" / "pythonw.exe"
        if win.is_file():
            return win
        exe = repo_root / "studio-api" / ".venv" / "Scripts" / "python.exe"
        if exe.is_file():
            return exe
    return None


def discover_qwen_folder(model_root: Path) -> tuple[Path | None, Path | None]:
    """Return (qwen_comfy_base, unet_file) under a configured model root. No hardcoded drive."""
    bases = [
        model_root / "Qwen" / "ComfyUI",
        model_root / "Qwen",
        model_root / "qwen",
    ]
    for base in bases:
        if not base.is_dir():
            continue
        for unet in base.rglob("qwen_image_edit_2509*.safetensors"):
            return base, unet
    return None, None


def build_discovered_config(*, repo_root: Path | None = None) -> RuntimeConfig:
    """Hint builder for Setup Wizard. Result still must pass validate_runtime_config."""
    comfy_root, comfy_py = discover_comfy_hint()
    model_root = discover_model_root_hint()
    service_py = discover_service_python_hint(repo_root)
    folders: dict[str, str] = {}
    yaml_folders = _folders_from_existing_yaml()
    if "adept_qwen_edit_2509" in yaml_folders:
        folders["qwen"] = str(yaml_folders["adept_qwen_edit_2509"])
    if "adept_krea2" in yaml_folders:
        folders["krea2"] = str(yaml_folders["adept_krea2"])
    if "adept_sd15" in yaml_folders:
        folders["sd15"] = str(yaml_folders["adept_sd15"])
    if "adept_sd15_controlnet" in yaml_folders:
        folders["sd15_controlnet"] = str(yaml_folders["adept_sd15_controlnet"])
    if model_root:
        qwen_base, _unet = discover_qwen_folder(model_root)
        if qwen_base is not None:
            folders.setdefault("qwen", str(qwen_base))
        krea = _first_dir(model_root / "krea2", model_root / "Krea2")
        if krea:
            folders.setdefault("krea2", str(krea))
        sd15 = _first_dir(model_root / "StableDiffusion15", model_root / "sd15")
        if sd15:
            folders.setdefault("sd15", str(sd15))
        sd15_cn = _first_dir(model_root / "ControlNet" / "SD15")
        if sd15_cn:
            folders.setdefault("sd15_controlnet", str(sd15_cn))
    api_python = ""
    api_root = ""
    if repo_root:
        win = repo_root / "studio-api" / ".venv" / "Scripts" / "python.exe"
        nix = repo_root / "studio-api" / ".venv" / "bin" / "python"
        if win.is_file():
            api_python = str(win)
        elif nix.is_file():
            api_python = str(nix)
        if (repo_root / "studio-api").is_dir():
            api_root = str(repo_root / "studio-api")
    return RuntimeConfig(
        comfyRoot=str(comfy_root or ""),
        comfyPython=str(comfy_py or ""),
        modelRoot=str(model_root or ""),
        logDir=str(default_log_dir()),
        stateDir=str(default_state_dir()),
        servicePython=str(service_py or ""),
        modelFolders=folders,
        repoRoot=str(repo_root or ""),
        autostart=True,
        studioApi=StudioApiSettings(
            enabled=True,
            python=api_python,
            appRoot=api_root,
            port=API_PORT,
        ),
    )
