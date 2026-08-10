"""Isolated IndexTTS2 runtime manager for Adept UI."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
import venv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ...config import settings

OFFICIAL_REPO_URL = "https://github.com/index-tts/index-tts"
PINNED_REPO_SHA = "13495845e3028f0bb6ca1462ad22aa0e76349e40"
MODEL_REPOSITORY = "IndexTeam/IndexTTS-2"
PROVIDER_ID = "index-tts2-local"
RUNTIME_SLUG = "index-tts2"
DEFAULT_DEVICE = "cuda:0"

REQUIRED_MODEL_FILES = (
    "config.yaml",
    "bpe.model",
    "gpt.pth",
    "s2mel.pth",
    "wav2vec2bert_stats.pt",
    "feat1.pt",
    "feat2.pt",
)
REQUIRED_MODEL_DIRS = ("qwen0.6bemo4-merge",)
REQUIRED_AUX_MODEL_FILES = (
    "hf_cache/semantic_codec_model.safetensors",
    "hf_cache/campplus_cn_common.bin",
    "hf_cache/bigvgan/config.json",
    "hf_cache/bigvgan/bigvgan_generator.pt",
)
REQUIRED_AUX_MODEL_DIRS = ("hf_cache/w2v-bert-2.0",)


class IndexTTS2RuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": dict(self.details)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json_load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def _manifest_int(payload: dict[str, Any], key: str) -> int:
    try:
        return max(0, int(payload.get(key) or 0))
    except Exception:
        return 0


InstallProgressCallback = Callable[[str, dict[str, Any]], None]


class IndexTTS2RuntimeManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_jobs: dict[str, dict[str, Any]] = {}

    @property
    def runtime_root(self) -> Path:
        return Path(settings.data_dir) / "runtimes" / RUNTIME_SLUG

    @property
    def environment_root(self) -> Path:
        return self.runtime_root / "environment"

    @property
    def models_root(self) -> Path:
        return self.runtime_root / "models"

    @property
    def manifests_root(self) -> Path:
        return self.runtime_root / "manifests"

    @property
    def logs_root(self) -> Path:
        return self.runtime_root / "logs"

    @property
    def outputs_root(self) -> Path:
        return self.runtime_root / "outputs"

    @property
    def repo_root(self) -> Path:
        return self.runtime_root / "repo"

    @property
    def venv_root(self) -> Path:
        return self.environment_root / "venv"

    @property
    def manifest_path(self) -> Path:
        return self.manifests_root / "index-tts2-manifest.json"

    @property
    def service_state_path(self) -> Path:
        return self.manifests_root / "index-tts2-service.json"

    @property
    def jobs_root(self) -> Path:
        return self.manifests_root / "jobs"

    @property
    def worker_script(self) -> Path:
        return Path(__file__).with_name("worker_infer.py")

    def _ensure_layout(self) -> None:
        for path in (
            self.runtime_root,
            self.environment_root,
            self.models_root,
            self.manifests_root,
            self.logs_root,
            self.outputs_root,
            self.repo_root,
            self.jobs_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _venv_python(self) -> Path:
        if os.name == "nt":
            return self.venv_root / "Scripts" / "python.exe"
        return self.venv_root / "bin" / "python"

    def _base_manifest(self) -> dict[str, Any]:
        return {
            "runtime": RUNTIME_SLUG,
            "providerId": PROVIDER_ID,
            "officialRepo": OFFICIAL_REPO_URL,
            "pinnedRevision": PINNED_REPO_SHA,
            "modelRepository": MODEL_REPOSITORY,
            "status": "not_installed",
            "installed": False,
            "runtimeReady": False,
            "createdAt": _now(),
            "updatedAt": _now(),
            "repoPath": str(self.repo_root),
            "environmentPath": str(self.environment_root),
            "modelsPath": str(self.models_root),
            "logsPath": str(self.logs_root),
            "outputsPath": str(self.outputs_root),
            "manifestsPath": str(self.manifests_root),
        }

    def _read_manifest(self) -> dict[str, Any]:
        return _safe_json_load(self.manifest_path)

    def _write_manifest(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = self._base_manifest()
        body.update(payload)
        body["updatedAt"] = _now()
        _safe_json_write(self.manifest_path, body)
        return body

    def _update_manifest(self, **changes: Any) -> dict[str, Any]:
        current = self._read_manifest() or self._base_manifest()
        current.update(changes)
        return self._write_manifest(current)

    def _log_path(self, prefix: str, suffix: str = ".log") -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return self.logs_root / f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}{suffix}"

    def _run_command(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        log_prefix: str | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        if log_prefix:
            _safe_json_write(
                self._log_path(log_prefix, ".json"),
                {
                    "command": command,
                    "cwd": str(cwd) if cwd else None,
                    "exitCode": result.returncode,
                    "stdout": (result.stdout or "")[-10000:],
                    "stderr": (result.stderr or "")[-10000:],
                    "at": _now(),
                },
            )
        if check and result.returncode != 0:
            raise IndexTTS2RuntimeError(
                "INDEX_TTS2_COMMAND_FAILED",
                f"Command failed: {' '.join(command)}",
                details={
                    "exitCode": result.returncode,
                    "stdout": (result.stdout or "")[-4000:],
                    "stderr": (result.stderr or "")[-4000:],
                },
            )
        return result

    def _git_revision(self) -> str | None:
        if not (self.repo_root / ".git").exists():
            return None
        result = self._run_command(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_root,
            check=False,
            log_prefix="repo-revision",
        )
        if result.returncode != 0:
            return None
        return (result.stdout or "").strip()[:40] or None

    def _git_origin(self) -> str | None:
        if not (self.repo_root / ".git").exists():
            return None
        result = self._run_command(
            ["git", "remote", "get-url", "origin"],
            cwd=self.repo_root,
            check=False,
            log_prefix="repo-origin",
        )
        if result.returncode != 0:
            return None
        return (result.stdout or "").strip() or None

    def _model_presence(self, manifest: dict[str, Any] | None = None, *, include_disk_usage: bool = True) -> dict[str, Any]:
        manifest = manifest or {}
        missing_files = [name for name in REQUIRED_MODEL_FILES if not (self.models_root / name).is_file()]
        missing_dirs = [name for name in REQUIRED_MODEL_DIRS if not (self.models_root / name).is_dir()]
        missing_aux_files = [name for name in REQUIRED_AUX_MODEL_FILES if not (self.models_root / name).is_file()]
        missing_aux_dirs = [name for name in REQUIRED_AUX_MODEL_DIRS if not (self.models_root / name).is_dir()]
        disk_usage = _manifest_int(manifest, "modelsDiskUsageBytes")
        if include_disk_usage or disk_usage <= 0:
            disk_usage = _dir_size(self.models_root)
        return {
            "allPresent": not (missing_files or missing_dirs or missing_aux_files or missing_aux_dirs),
            "missingFiles": missing_files,
            "missingDirs": missing_dirs,
            "missingAuxFiles": missing_aux_files,
            "missingAuxDirs": missing_aux_dirs,
            "modelsDiskUsageBytes": disk_usage,
        }

    def _service_snapshot(self) -> dict[str, Any]:
        state = _safe_json_load(self.service_state_path)
        try:
            pid = int(state.get("pid") or 0)
        except Exception:
            pid = 0
        state["running"] = _pid_alive(pid)
        return state

    def inspect_installation(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_layout()
            manifest = self._read_manifest()
            state_hint = str(manifest.get("status") or "")
            fast_snapshot_ok = bool(manifest) and state_hint not in {"installing", "checking", "verifying"}
            repo_revision = (
                str(manifest.get("repoRevision") or "").strip() or None
                if fast_snapshot_ok
                else self._git_revision()
            )
            repo_origin = (
                str(manifest.get("repoOrigin") or "").strip() or None
                if fast_snapshot_ok
                else self._git_origin()
            )
            repo_exists = (self.repo_root / ".git").exists()
            venv_python = self._venv_python()
            venv_ok = venv_python.is_file()
            models = self._model_presence(manifest, include_disk_usage=not fast_snapshot_ok)
            import_ok = bool((manifest.get("importProbe") or {}).get("ok"))
            service = self._service_snapshot()
            footprint = repo_exists or venv_ok or models["modelsDiskUsageBytes"] > 0
            if state_hint in {"installing", "checking", "verifying"}:
                state = state_hint
            elif not footprint and not manifest:
                state = "not_installed"
            elif repo_exists and repo_origin and repo_origin != OFFICIAL_REPO_URL:
                state = "incompatible"
            elif repo_exists and repo_revision and repo_revision != PINNED_REPO_SHA:
                state = "update_available"
            elif repo_exists and venv_ok and import_ok and models["allPresent"]:
                state = "ready" if bool((manifest.get("lastHealth") or {}).get("ok")) else "installed"
            elif repo_exists and venv_ok and import_ok:
                state = "compatible"
            elif footprint:
                state = "repair_required"
            else:
                state = "not_installed"
            return {
                "state": state,
                "status": state,
                "installed": state in {"compatible", "installed", "ready"},
                "runtimeReady": state == "ready",
                "providerId": PROVIDER_ID,
                "pinnedRevision": PINNED_REPO_SHA,
                "modelRepository": MODEL_REPOSITORY,
                "message": {
                    "not_installed": "IndexTTS2 has not been installed yet.",
                    "compatible": "IndexTTS2 runtime is installed but model assets are not complete yet.",
                    "installed": "IndexTTS2 runtime is installed and awaiting verification.",
                    "ready": "IndexTTS2 runtime is ready for isolated inference.",
                    "repair_required": "IndexTTS2 runtime needs repair before use.",
                    "incompatible": "The runtime repo origin is not the locked official upstream.",
                    "update_available": "The runtime repo revision does not match the locked pin.",
                    "installing": "IndexTTS2 installation is in progress.",
                    "checking": "IndexTTS2 runtime check is in progress.",
                    "verifying": "IndexTTS2 verification is in progress.",
                    "failed": "IndexTTS2 installation failed.",
                }.get(state, state),
                "paths": {
                    "runtimeRoot": str(self.runtime_root),
                    "environment": str(self.environment_root),
                    "venvPython": str(venv_python) if venv_ok else None,
                    "models": str(self.models_root),
                    "repo": str(self.repo_root),
                    "logs": str(self.logs_root),
                    "outputs": str(self.outputs_root),
                    "manifest": str(self.manifest_path),
                },
                "repo": {
                    "exists": repo_exists,
                    "origin": repo_origin,
                    "originOfficial": repo_origin == OFFICIAL_REPO_URL,
                    "revision": repo_revision,
                    "pinnedRevision": PINNED_REPO_SHA,
                },
                "models": models,
                "manifest": manifest,
                "service": service,
                "lastHealth": manifest.get("lastHealth") or {},
                "diskUsageBytes": {
                    "environment": _manifest_int(manifest, "environmentDiskUsageBytes"),
                    "models": models["modelsDiskUsageBytes"],
                    "repo": _manifest_int(manifest, "repoDiskUsageBytes"),
                    "logs": _manifest_int(manifest, "logsDiskUsageBytes"),
                    "outputs": _manifest_int(manifest, "outputsDiskUsageBytes"),
                },
                "activeJobs": len(self._active_jobs),
            }

    def _clone_repo(self, *, force: bool = False) -> dict[str, Any]:
        repo_git = self.repo_root / ".git"
        if self.repo_root.exists() and any(self.repo_root.iterdir()) and not repo_git.exists():
            if not force:
                raise IndexTTS2RuntimeError(
                    "INDEX_TTS2_REPO_DIR_INVALID",
                    "The runtime repo directory exists but is not a git checkout.",
                    details={"path": str(self.repo_root)},
                )
            shutil.rmtree(self.repo_root, ignore_errors=True)
            self.repo_root.mkdir(parents=True, exist_ok=True)
        if not repo_git.exists():
            self._run_command(
                ["git", "clone", OFFICIAL_REPO_URL, str(self.repo_root)],
                cwd=self.runtime_root,
                check=True,
                log_prefix="repo-clone",
            )
        elif self._git_origin() != OFFICIAL_REPO_URL:
            if force:
                shutil.rmtree(self.repo_root, ignore_errors=True)
                self._run_command(
                    ["git", "clone", OFFICIAL_REPO_URL, str(self.repo_root)],
                    cwd=self.runtime_root,
                    check=True,
                    log_prefix="repo-reclone",
                )
                repo_git = self.repo_root / ".git"
            else:
                raise IndexTTS2RuntimeError(
                    "INDEX_TTS2_REPO_ORIGIN_MISMATCH",
                    "The runtime repo origin is not the locked official upstream.",
                    details={"origin": self._git_origin(), "expected": OFFICIAL_REPO_URL},
                )
        if self._git_revision() != PINNED_REPO_SHA:
            self._run_command(
                ["git", "fetch", "origin", PINNED_REPO_SHA],
                cwd=self.repo_root,
                check=False,
                log_prefix="repo-fetch",
            )
            self._run_command(
                ["git", "checkout", "--detach", PINNED_REPO_SHA],
                cwd=self.repo_root,
                check=True,
                log_prefix="repo-checkout",
            )
        lfs = self._run_command(
            ["git", "lfs", "version"],
            cwd=self.repo_root,
            check=False,
            log_prefix="repo-lfs-version",
        )
        lfs_result = {"available": lfs.returncode == 0, "message": (lfs.stdout or lfs.stderr or "").strip()[:500]}
        if lfs.returncode == 0:
            pull = self._run_command(
                ["git", "lfs", "pull"],
                cwd=self.repo_root,
                check=False,
                log_prefix="repo-lfs-pull",
            )
            lfs_result["pullExitCode"] = pull.returncode
            lfs_result["pullMessage"] = (pull.stdout or pull.stderr or "").strip()[:1000]
        return {"origin": self._git_origin(), "revision": self._git_revision(), "lfs": lfs_result}

    def _ensure_venv(self) -> Path:
        if not self.venv_root.exists():
            venv.create(self.venv_root, with_pip=True)
        venv_python = self._venv_python()
        if not venv_python.is_file():
            raise IndexTTS2RuntimeError("INDEX_TTS2_VENV_MISSING", "The isolated virtual environment python is missing.")
        return venv_python

    def _install_repo_dependencies(self, venv_python: Path) -> dict[str, Any]:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        self._run_command(
            [str(venv_python), "-m", "pip", "install", "-U", "pip", "setuptools", "wheel", "uv"],
            cwd=self.repo_root,
            env=env,
            check=True,
            log_prefix="pip-bootstrap",
        )
        uv_result = self._run_command(
            [str(venv_python), "-m", "uv", "pip", "install", "--python", str(venv_python), "-e", str(self.repo_root)],
            cwd=self.repo_root,
            env=env,
            check=False,
            log_prefix="uv-install",
        )
        method = "uv"
        if uv_result.returncode != 0:
            method = "pip"
            self._run_command(
                [str(venv_python), "-m", "pip", "install", "-e", str(self.repo_root)],
                cwd=self.repo_root,
                env=env,
                check=True,
                log_prefix="pip-install-fallback",
            )
        return {"installMethod": method, "uvExitCode": uv_result.returncode}

    def _import_probe(self, venv_python: Path) -> dict[str, Any]:
        script = (
            "import importlib, json\n"
            "mods = {}\n"
            "for name in ('torch','torchaudio','indextts'):\n"
            "    try:\n"
            "        mod = importlib.import_module(name)\n"
            "        mods[name] = getattr(mod, '__version__', 'ok')\n"
            "    except Exception as exc:\n"
            "        print(json.dumps({'ok': False, 'module': name, 'error': str(exc)}))\n"
            "        raise SystemExit(1)\n"
            "print(json.dumps({'ok': True, 'modules': mods}))\n"
        )
        result = self._run_command(
            [str(venv_python), "-c", script],
            cwd=self.repo_root,
            check=False,
            log_prefix="import-probe",
        )
        try:
            payload = json.loads((result.stdout or "").strip().splitlines()[-1])
        except Exception:
            payload = {
                "ok": result.returncode == 0,
                "stdout": (result.stdout or "")[-1000:],
                "stderr": (result.stderr or "")[-1000:],
            }
        payload["exitCode"] = result.returncode
        return payload

    def _download_models(self, venv_python: Path) -> dict[str, Any]:
        script = (
            "import json\n"
            "from huggingface_hub import snapshot_download\n"
            "from indextts.utils.model_download import ensure_models_available\n"
            f"repo_id = {MODEL_REPOSITORY!r}\n"
            f"model_dir = {str(self.models_root)!r}\n"
            "snapshot_path = snapshot_download(repo_id=repo_id, local_dir=model_dir)\n"
            "aux = ensure_models_available(model_dir)\n"
            "print(json.dumps({'ok': True, 'path': snapshot_path, 'aux': aux}, ensure_ascii=False))\n"
        )
        result = self._run_command(
            [str(venv_python), "-c", script],
            cwd=self.repo_root,
            check=True,
            log_prefix="download-models",
        )
        payload: dict[str, Any] = {"ok": True}
        lines = (result.stdout or "").strip().splitlines()
        if lines:
            try:
                payload = json.loads(lines[-1])
            except Exception:
                pass
        payload["downloadedAt"] = _now()
        payload["modelsDiskUsageBytes"] = _dir_size(self.models_root)
        return payload

    def install(
        self,
        *,
        confirm: bool = False,
        confirm_download_models: bool = False,
        force: bool = False,
        progress_callback: InstallProgressCallback | None = None,
    ) -> dict[str, Any]:
        if not confirm:
            raise IndexTTS2RuntimeError(
                "INDEX_TTS2_CONFIRM_REQUIRED",
                "IndexTTS2 installation requires explicit confirmation.",
            )

        def emit(phase: str, **details: Any) -> None:
            if progress_callback:
                progress_callback(phase, dict(details))

        with self._lock:
            self._ensure_layout()
            self._update_manifest(status="installing", installed=False, runtimeReady=False, lastError=None)
            evidence: dict[str, Any] = {
                "providerId": PROVIDER_ID,
                "officialRepo": OFFICIAL_REPO_URL,
                "pinnedRevision": PINNED_REPO_SHA,
                "modelRepository": MODEL_REPOSITORY,
                "startedAt": _now(),
                "confirmDownloadModels": bool(confirm_download_models),
            }
            try:
                emit(
                    "clone_repo",
                    step=1,
                    totalSteps=4,
                    message="Cloning the pinned IndexTTS2 repository.",
                )
                repo = self._clone_repo(force=force)
                emit(
                    "create_environment",
                    step=1,
                    totalSteps=4,
                    message="Preparing the isolated Python environment.",
                )
                venv_python = self._ensure_venv()
                emit(
                    "install_dependencies",
                    step=2,
                    totalSteps=4,
                    message="Installing IndexTTS2 runtime dependencies.",
                )
                deps = self._install_repo_dependencies(venv_python)
                emit(
                    "import_probe",
                    step=3,
                    totalSteps=4,
                    message="Verifying the isolated runtime import probe.",
                )
                import_probe = self._import_probe(venv_python)
                if not import_probe.get("ok"):
                    raise IndexTTS2RuntimeError(
                        "INDEX_TTS2_IMPORT_PROBE_FAILED",
                        "The isolated IndexTTS2 environment failed its import probe.",
                        details=import_probe,
                    )
                evidence.update(
                    {
                        "repo": repo,
                        "venvPython": str(venv_python),
                        "dependencies": deps,
                        "importProbe": import_probe,
                    }
                )
                state = "compatible"
                if confirm_download_models:
                    emit(
                        "download_models",
                        step=4,
                        totalSteps=4,
                        message="Downloading required IndexTTS2 model files.",
                    )
                    evidence["models"] = self._download_models(venv_python)
                    if not self._model_presence()["allPresent"]:
                        raise IndexTTS2RuntimeError(
                            "INDEX_TTS2_MODEL_DOWNLOAD_INCOMPLETE",
                            "The model download completed without all required files.",
                        )
                    state = "installed"
                manifest = self._update_manifest(
                    status=state,
                    installed=True,
                    runtimeReady=False,
                    repoRevision=repo.get("revision"),
                    repoOrigin=repo.get("origin"),
                    venvPython=str(venv_python),
                    dependenciesInstalled=True,
                    importProbe=import_probe,
                    environmentDiskUsageBytes=_dir_size(self.environment_root),
                    repoDiskUsageBytes=_dir_size(self.repo_root),
                    logsDiskUsageBytes=_dir_size(self.logs_root),
                    outputsDiskUsageBytes=_dir_size(self.outputs_root),
                    downloadModelsDeferred=not confirm_download_models,
                    installMode="scaffold_only" if not confirm_download_models else "full",
                    lastInstallAt=_now(),
                )
                evidence["manifest"] = manifest
                emit(
                    "verify_runtime",
                    step=4,
                    totalSteps=4,
                    message=(
                        "Verifying the full runtime install."
                        if confirm_download_models
                        else "Runtime scaffold complete. Model download remains deferred."
                    ),
                )
                inspection = self.verify() if confirm_download_models else self.inspect_installation()
                return {
                    "ok": True,
                    "state": inspection.get("state"),
                    "providerId": PROVIDER_ID,
                    "downloadDeferred": not confirm_download_models,
                    "message": (
                        "IndexTTS2 runtime scaffolded successfully. Model download is still required before inference."
                        if not confirm_download_models
                        else "IndexTTS2 runtime installed and verified."
                    ),
                    "evidence": evidence,
                }
            except Exception as exc:  # noqa: BLE001
                error = exc if isinstance(exc, IndexTTS2RuntimeError) else IndexTTS2RuntimeError(
                    "INDEX_TTS2_INSTALL_FAILED",
                    f"IndexTTS2 install failed: {exc}",
                )
                self._update_manifest(status="failed", installed=False, runtimeReady=False, lastError=error.to_dict())
                return {
                    "ok": False,
                    "state": "failed",
                    "providerId": PROVIDER_ID,
                    "error": error.to_dict(),
                    "evidence": evidence,
                }

    def _run_health_probe(self, *, allow_cpu_fallback: bool = False) -> dict[str, Any]:
        venv_python = self._venv_python()
        if not venv_python.is_file():
            raise IndexTTS2RuntimeError("INDEX_TTS2_VENV_MISSING", "IndexTTS2 is missing its isolated python runtime.")
        health_path = self.manifests_root / f"health-{uuid.uuid4().hex[:10]}.json"
        command = [
            str(venv_python),
            str(self.worker_script),
            "--health-json",
            str(health_path),
            "--model-dir",
            str(self.models_root),
            "--repo-dir",
            str(self.repo_root),
        ]
        if allow_cpu_fallback:
            command.append("--allow-cpu-fallback")
        result = self._run_command(
            command,
            cwd=self.repo_root if self.repo_root.exists() else self.runtime_root,
            check=False,
            log_prefix="health-probe",
            timeout=300,
        )
        payload = _safe_json_load(health_path)
        if not payload:
            raise IndexTTS2RuntimeError(
                "INDEX_TTS2_HEALTH_PROBE_FAILED",
                "IndexTTS2 health probe did not return a usable response.",
                details={
                    "exitCode": result.returncode,
                    "stdout": (result.stdout or "")[-1000:],
                    "stderr": (result.stderr or "")[-1000:],
                },
            )
        payload["exitCode"] = result.returncode
        return payload

    def health_check(self, *, allow_cpu_fallback: bool = False) -> dict[str, Any]:
        with self._lock:
            inspection = self.inspect_installation()
            if inspection["state"] == "not_installed":
                return {
                    "ok": False,
                    "installed": False,
                    "runtimeReady": False,
                    "providerId": PROVIDER_ID,
                    "code": "INDEX_TTS2_NOT_INSTALLED",
                    "message": "IndexTTS2 is not installed.",
                }
            if inspection["state"] == "incompatible":
                return {
                    "ok": False,
                    "installed": False,
                    "runtimeReady": False,
                    "providerId": PROVIDER_ID,
                    "code": "INDEX_TTS2_INCOMPATIBLE_INSTALL",
                    "message": inspection["message"],
                }
            if not inspection["models"]["allPresent"]:
                return {
                    "ok": False,
                    "installed": True,
                    "runtimeReady": False,
                    "providerId": PROVIDER_ID,
                    "code": "INDEX_TTS2_MODELS_MISSING",
                    "message": "IndexTTS2 model resources are incomplete.",
                    "details": inspection["models"],
                }
            self._update_manifest(status="checking")
            payload = self._run_health_probe(allow_cpu_fallback=allow_cpu_fallback)
            self._update_manifest(
                status="ready" if payload.get("ok") else "installed",
                installed=True,
                runtimeReady=bool(payload.get("ok")),
                lastHealth=payload,
                lastHealthAt=_now(),
            )
            return payload

    def verify(self) -> dict[str, Any]:
        with self._lock:
            self._update_manifest(status="verifying")
            health = self.health_check()
            inspection = self.inspect_installation()
            inspection["health"] = health
            return inspection

    def repair(self, *, confirm: bool = False, confirm_download_models: bool = False) -> dict[str, Any]:
        return self.install(confirm=confirm, confirm_download_models=confirm_download_models, force=True)

    def remove(self) -> dict[str, Any]:
        with self._lock:
            self.stop()
            existed = self.runtime_root.exists()
            if existed:
                shutil.rmtree(self.runtime_root, ignore_errors=True)
            return {
                "ok": True,
                "removed": existed,
                "providerId": PROVIDER_ID,
                "runtimeRoot": str(self.runtime_root),
                "at": _now(),
            }

    def open_logs(self) -> str:
        self._ensure_layout()
        return str(self.logs_root)

    def _terminate_pid(self, pid: int) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    def start(self) -> dict[str, Any]:
        with self._lock:
            health = self.health_check()
            if not health.get("installed"):
                return {
                    "ok": False,
                    "providerId": PROVIDER_ID,
                    "message": health.get("message") or "IndexTTS2 is not installed.",
                }
            current = self._service_snapshot()
            try:
                current_pid = int(current.get("pid") or 0)
            except Exception:
                current_pid = 0
            if _pid_alive(current_pid):
                return {
                    "ok": True,
                    "running": True,
                    "providerId": PROVIDER_ID,
                    "pid": current_pid,
                    "logPath": current.get("logPath"),
                }
            venv_python = self._venv_python()
            log_path = self._log_path("adapter-process")
            health_json = self.manifests_root / "adapter-process-health.json"
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            log_handle = log_path.open("a", encoding="utf-8")
            process = subprocess.Popen(
                [
                    str(venv_python),
                    str(self.worker_script),
                    "--adapter-process",
                    "--health-json",
                    str(health_json),
                    "--model-dir",
                    str(self.models_root),
                    "--repo-dir",
                    str(self.repo_root),
                ],
                cwd=str(self.repo_root if self.repo_root.exists() else self.runtime_root),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                stdout=log_handle,
                stderr=log_handle,
                text=True,
                creationflags=creationflags,
            )
            state = {
                "pid": process.pid,
                "startedAt": _now(),
                "logPath": str(log_path),
                "healthJson": str(health_json),
            }
            _safe_json_write(self.service_state_path, state)
            self._update_manifest(service=state)
            return {
                "ok": True,
                "running": True,
                "providerId": PROVIDER_ID,
                "pid": process.pid,
                "logPath": str(log_path),
            }

    def stop(self) -> dict[str, Any]:
        with self._lock:
            state = self._service_snapshot()
            try:
                pid = int(state.get("pid") or 0)
            except Exception:
                pid = 0
            if not pid or not _pid_alive(pid):
                return {"ok": True, "running": False, "providerId": PROVIDER_ID}
            self._terminate_pid(pid)
            for _ in range(50):
                if not _pid_alive(pid):
                    break
                time.sleep(0.1)
            _safe_json_write(
                self.service_state_path,
                {"pid": pid, "stoppedAt": _now(), "logPath": state.get("logPath")},
            )
            return {"ok": True, "running": False, "providerId": PROVIDER_ID, "pid": pid}

    def restart(self) -> dict[str, Any]:
        self.stop()
        return self.start()

    def _job_path(self, job_id: str) -> Path:
        return self.jobs_root / f"{job_id}.json"

    def _normalize_request(self, request: dict[str, Any] | Any) -> dict[str, Any]:
        raw = dict(request) if isinstance(request, dict) else dict(getattr(request, "__dict__", {}) or {})
        return {
            "jobId": str(raw.get("jobId") or f"indextts2_{uuid.uuid4().hex[:12]}"),
            "projectId": str(raw.get("projectId") or "").strip() or None,
            "text": str(raw.get("text") or raw.get("prompt") or "").strip(),
            "referenceAudioPath": str(
                raw.get("referenceAudioPath")
                or raw.get("voice")
                or raw.get("voicePath")
                or raw.get("spk_audio_prompt")
                or ""
            ).strip(),
            "emotionAudioPath": str(
                raw.get("emotionAudioPath")
                or raw.get("emotion_audio")
                or raw.get("emo_audio_prompt")
                or ""
            ).strip()
            or None,
            "emotionText": str(
                raw.get("emotionText")
                or raw.get("emotional_direction")
                or raw.get("performance_instruction")
                or raw.get("stylePrompt")
                or ""
            ).strip()
            or None,
            "outputPath": str(raw.get("outputPath") or "").strip(),
            "format": str(raw.get("format") or "wav").lower(),
            "allowCpuFallback": bool(
                raw.get("allow_cpu_fallback") or raw.get("allowCpuFallback") or raw.get("cpuFallbackApproved")
            ),
            "device": str(raw.get("device") or DEFAULT_DEVICE).strip(),
            "useFp16": bool(raw.get("useFp16", True)),
            "retryOf": raw.get("retryOf"),
            "metadata": dict(raw.get("metadata") or {}),
        }

    def get_job(self, job_id: str) -> dict[str, Any]:
        payload = _safe_json_load(self._job_path(job_id))
        if payload:
            return payload
        return {
            "ok": False,
            "error": {"code": "INDEX_TTS2_JOB_NOT_FOUND", "message": f"Job {job_id} was not found."},
        }

    def _build_not_installed_error(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": "INDEX_TTS2_NOT_INSTALLED",
                "message": "IndexTTS2 is not installed. Install the isolated runtime first.",
                "providerId": PROVIDER_ID,
            },
        }

    def _finalize_job_failure(
        self,
        payload: dict[str, Any],
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload.update(
            {
                "ok": False,
                "status": "failed",
                "finishedAt": _now(),
                "error": {"code": code, "message": message, "details": dict(details or {})},
            }
        )
        _safe_json_write(self._job_path(payload["jobId"]), payload)
        return payload

    def generate_take(self, request: dict[str, Any] | Any) -> dict[str, Any]:
        normalized = self._normalize_request(request)
        with self._lock:
            if self.inspect_installation()["state"] == "not_installed":
                return self._build_not_installed_error()
            if not normalized["text"]:
                return {
                    "ok": False,
                    "error": {"code": "INDEX_TTS2_TEXT_REQUIRED", "message": "Text is required for IndexTTS2 synthesis."},
                }
            if not normalized["referenceAudioPath"]:
                return {
                    "ok": False,
                    "error": {
                        "code": "INDEX_TTS2_REFERENCE_REQUIRED",
                        "message": "A local reference audio path is required for IndexTTS2 synthesis.",
                    },
                }
            health = self.health_check(allow_cpu_fallback=normalized["allowCpuFallback"])
            if not health.get("ok"):
                return {
                    "ok": False,
                    "error": {
                        "code": health.get("code") or "INDEX_TTS2_RUNTIME_UNAVAILABLE",
                        "message": health.get("message") or "IndexTTS2 runtime is not ready.",
                        "details": health.get("details") or health,
                    },
                }
            output_path = Path(normalized["outputPath"]) if normalized["outputPath"] else self.outputs_root / f"{normalized['jobId']}.wav"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            job = {
                "jobId": normalized["jobId"],
                "providerId": PROVIDER_ID,
                "status": "queued",
                "ok": False,
                "createdAt": _now(),
                "request": normalized,
                "runtime": {
                    "repoDir": str(self.repo_root),
                    "modelDir": str(self.models_root),
                    "venvPython": str(self._venv_python()),
                    "pinnedRevision": PINNED_REPO_SHA,
                    "providerId": PROVIDER_ID,
                },
                "output": {"path": str(output_path), "format": "wav"},
                "logPath": str(self._log_path(f"job-{normalized['jobId']}")),
            }
            job_path = self._job_path(normalized["jobId"])
            _safe_json_write(job_path, job)
            log_handle = Path(job["logPath"]).open("a", encoding="utf-8")
            process = subprocess.Popen(
                [str(self._venv_python()), str(self.worker_script), "--job-json", str(job_path)],
                cwd=str(self.repo_root if self.repo_root.exists() else self.runtime_root),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                stdout=log_handle,
                stderr=log_handle,
                text=True,
            )
            self._active_jobs[job["jobId"]] = {
                "process": process,
                "pid": process.pid,
                "jobPath": str(job_path),
                "logPath": job["logPath"],
            }
        returncode = process.wait()
        with self._lock:
            self._active_jobs.pop(job["jobId"], None)
            payload = _safe_json_load(job_path) or dict(job)
            if returncode != 0 and not payload.get("ok"):
                return self._finalize_job_failure(
                    payload,
                    "INDEX_TTS2_INFERENCE_FAILED",
                    "IndexTTS2 worker exited without producing a successful output.",
                    details={"exitCode": returncode, "logPath": job["logPath"]},
                )
            return payload

    def generate_scene(self, request: dict[str, Any] | Any) -> dict[str, Any]:
        raw = dict(request) if isinstance(request, dict) else dict(getattr(request, "__dict__", {}) or {})
        takes = raw.get("takes") or raw.get("segments") or raw.get("items") or []
        if not isinstance(takes, list):
            return {
                "ok": False,
                "error": {"code": "INDEX_TTS2_BATCH_INVALID", "message": "Batch request must provide a list of takes."},
            }
        results = []
        failed = 0
        for idx, take in enumerate(takes):
            body = dict(take or {})
            body.setdefault("jobId", f"indextts2_scene_{idx + 1}_{uuid.uuid4().hex[:8]}")
            if not body.get("outputPath"):
                body["outputPath"] = str(self.outputs_root / f"{body['jobId']}.wav")
            result = self.generate_take(body)
            results.append(result)
            if not result.get("ok"):
                failed += 1
                if not raw.get("continueOnError"):
                    break
        return {
            "ok": failed == 0,
            "providerId": PROVIDER_ID,
            "count": len(results),
            "failed": failed,
            "results": results,
        }

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            active = self._active_jobs.get(job_id)
            payload = _safe_json_load(self._job_path(job_id))
            if not payload:
                return {
                    "ok": False,
                    "error": {"code": "INDEX_TTS2_JOB_NOT_FOUND", "message": f"Job {job_id} was not found."},
                }
            if active:
                try:
                    active["process"].terminate()
                except Exception:
                    pass
            payload["status"] = "cancelled"
            payload["finishedAt"] = _now()
            payload["ok"] = False
            payload["error"] = {"code": "INDEX_TTS2_CANCELLED", "message": "Job cancelled by user."}
            _safe_json_write(self._job_path(job_id), payload)
            return {"ok": True, "jobId": job_id, "status": "cancelled"}

    def retry(self, job_id: str) -> dict[str, Any]:
        existing = self.get_job(job_id)
        if not existing.get("request"):
            return existing
        body = dict(existing["request"])
        body["retryOf"] = job_id
        body["jobId"] = f"{job_id}_retry_{uuid.uuid4().hex[:6]}"
        return self.generate_take(body)

    def path_link(self, *, repo_path: str | None = None, model_path: str | None = None) -> dict[str, Any]:
        with self._lock:
            self._ensure_layout()
            linked: dict[str, str] = {}
            if repo_path:
                src = Path(repo_path)
                if not src.exists():
                    raise IndexTTS2RuntimeError(
                        "INDEX_TTS2_REPO_LINK_MISSING",
                        "The requested repo link source does not exist.",
                        details={"path": str(src)},
                    )
                if any(self.repo_root.iterdir()):
                    raise IndexTTS2RuntimeError(
                        "INDEX_TTS2_REPO_LINK_TARGET_NOT_EMPTY",
                        "The runtime repo directory must be empty before linking.",
                        details={"path": str(self.repo_root)},
                    )
                self._link_directory(src, self.repo_root)
                linked["repo"] = str(src)
            if model_path:
                src = Path(model_path)
                if not src.exists():
                    raise IndexTTS2RuntimeError(
                        "INDEX_TTS2_MODEL_LINK_MISSING",
                        "The requested model link source does not exist.",
                        details={"path": str(src)},
                    )
                if any(self.models_root.iterdir()):
                    raise IndexTTS2RuntimeError(
                        "INDEX_TTS2_MODEL_LINK_TARGET_NOT_EMPTY",
                        "The runtime models directory must be empty before linking.",
                        details={"path": str(self.models_root)},
                    )
                self._link_directory(src, self.models_root)
                linked["models"] = str(src)
            manifest = self._update_manifest(pathLinks=linked or None)
            return {"ok": True, "providerId": PROVIDER_ID, "linked": linked, "manifest": manifest}

    def _link_directory(self, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            self._run_command(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                cwd=target.parent,
                check=True,
                log_prefix="path-link",
            )
            return
        target.symlink_to(source, target_is_directory=True)

    def capability_metadata(self) -> dict[str, Any]:
        return {
            "providerId": PROVIDER_ID,
            "providerKey": PROVIDER_ID,
            "modelRepository": MODEL_REPOSITORY,
            "officialRepo": OFFICIAL_REPO_URL,
            "pinnedRevision": PINNED_REPO_SHA,
            "language": {
                "english": "recommended",
                "chinese": "recommended",
                "accent": "experimental",
                "mixed_language": "not_recommended",
            },
            "performance": {"emotion": "strong", "voice_cloning": "strong"},
            "formats": {"inputReference": ["wav", "mp3", "flac", "m4a"], "output": ["wav"]},
            "notes": [
                "Requires a local reference voice clip.",
                "Large isolated runtime with official pinned upstream clone.",
                "CPU execution is blocked by default unless explicitly approved.",
            ],
        }


_RUNTIME: IndexTTS2RuntimeManager | None = None
_RUNTIME_LOCK = threading.Lock()


def get_index_tts2_runtime() -> IndexTTS2RuntimeManager:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = IndexTTS2RuntimeManager()
        return _RUNTIME


def runtime_status() -> dict[str, Any]:
    runtime = get_index_tts2_runtime()
    inspection = runtime.inspect_installation()
    capability_metadata = runtime.capability_metadata()
    return {
        "ok": True,
        "providerId": PROVIDER_ID,
        "providerVersion": "m4.10-index-tts2",
        "installed": bool(inspection.get("installed")),
        "ready": inspection.get("state") == "ready",
        "availableOnDisk": bool((inspection.get("repo") or {}).get("exists")) or bool(
            (inspection.get("models") or {}).get("modelsDiskUsageBytes")
        ),
        "modelRevision": (inspection.get("repo") or {}).get("revision") or PINNED_REPO_SHA,
        "runtimeRoot": str(runtime.runtime_root),
        "manifestPath": str(runtime.manifest_path),
        "message": inspection.get("message") or inspection.get("state"),
        "language": capability_metadata.get("language") or {},
        "capabilityMetadata": capability_metadata,
        "mock": False,
    }


def install_runtime(*, confirm: bool, confirm_download_models: bool = False) -> dict[str, Any]:
    return get_index_tts2_runtime().install(
        confirm=confirm,
        confirm_download_models=confirm_download_models,
    )


def verify_runtime() -> dict[str, Any]:
    inspection = get_index_tts2_runtime().verify()
    status = runtime_status()
    status["verified"] = bool(inspection.get("runtimeReady"))
    status["inspection"] = inspection
    return status


def _wav_duration_ms(path: str) -> int | None:
    import wave

    try:
        with wave.open(path, "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate() or 1
            return int(1000 * frames / rate)
    except Exception:
        return None


def _resolve_reference_audio(db: Any, voice_identity_id: str | None) -> str:
    if db is None or not voice_identity_id:
        return ""
    try:
        from ...character_identity.models import VoiceProfileRow
        from ...db import Asset
    except Exception:
        return ""
    voice = db.get(VoiceProfileRow, voice_identity_id)
    if not voice:
        return ""
    candidate_ids = [
        getattr(voice, "reference_asset_id", None),
        getattr(voice, "approved_preview_asset_id", None),
    ]
    for asset_id in candidate_ids:
        if not asset_id:
            continue
        asset = db.get(Asset, asset_id)
        if asset and asset.path and Path(asset.path).is_file():
            return str(asset.path)
    lineage = getattr(voice, "lineage_json", None)
    if lineage:
        try:
            data = json.loads(lineage)
        except Exception:
            data = {}
        path = str(data.get("reference_path") or "")
        if path and Path(path).is_file():
            return path
    return ""


def generate_take(db: Any = None, **kwargs: Any) -> dict[str, Any]:
    manager = get_index_tts2_runtime()
    status = runtime_status()
    reference_audio = str(
        kwargs.get("referenceAudioPath")
        or kwargs.get("voice")
        or kwargs.get("reference_path")
        or _resolve_reference_audio(db, kwargs.get("voice_identity_id"))
        or ""
    ).strip()
    performance_plan = kwargs.get("performance_plan") or {}
    emotion_text = " ".join(
        str(performance_plan.get(key) or "").strip()
        for key in ("summary", "delivery", "notes")
        if str(performance_plan.get(key) or "").strip()
    ).strip()
    result = manager.generate_take(
        {
            "jobId": kwargs.get("take_id") or f"m410_{uuid.uuid4().hex[:12]}",
            "projectId": kwargs.get("project_id"),
            "text": kwargs.get("dialogue_text") or kwargs.get("text") or "",
            "referenceAudioPath": reference_audio,
            "emotionAudioPath": kwargs.get("emotion_audio_path") or kwargs.get("emotionAudioPath"),
            "emotionText": emotion_text or None,
            "emotionVector": kwargs.get("emotion_vector") or kwargs.get("emotionVector"),
            "emotionalReferenceStrength": kwargs.get("emotional_reference_strength"),
            "allowCpuFallback": bool(kwargs.get("allowCpuFallback") or kwargs.get("allow_cpu_fallback")),
        }
    )
    audio_asset_id = None
    duration_ms = None
    output_path = ""
    if result.get("ok"):
        output_path = str(((result.get("output") or {}).get("path")) or "")
        duration_ms = _wav_duration_ms(output_path) if output_path else None
        if db is not None and output_path and kwargs.get("project_id"):
            from ...db import Asset, Job

            audio_asset_id = str(uuid.uuid4())
            asset = Asset(
                id=audio_asset_id,
                project_id=str(kwargs["project_id"]),
                tag="dialogue",
                kind="audio",
                filename=Path(output_path).name,
                path=output_path,
                prompt_meta_json=json.dumps(
                    {
                        "source": "voice_performance.m410.index_tts2",
                        "recordId": kwargs.get("record_id"),
                        "takeId": kwargs.get("take_id"),
                    }
                ),
            )
            db.add(asset)
            job = Job(
                id=str(result.get("jobId") or kwargs.get("take_id") or uuid.uuid4()),
                project_id=str(kwargs["project_id"]),
                scene_id=kwargs.get("scene_id"),
                kind="voice_performance.index_tts2",
                status="completed",
                progress=1.0,
                message="completed",
                preview_json=json.dumps(
                    {
                        "audioAssetId": audio_asset_id,
                        "durationMs": duration_ms,
                        "outputPath": output_path,
                    }
                ),
                params_json=json.dumps(kwargs),
                output_path=output_path,
                updated_at=datetime.utcnow(),
            )
            db.merge(job)
            db.commit()
    else:
        if db is not None and kwargs.get("project_id"):
            from ...db import Job

            job = Job(
                id=str(result.get("jobId") or kwargs.get("take_id") or uuid.uuid4()),
                project_id=str(kwargs["project_id"]),
                scene_id=kwargs.get("scene_id"),
                kind="voice_performance.index_tts2",
                status="failed",
                progress=0.0,
                message=str(((result.get("error") or {}).get("message")) or "failed"),
                preview_json=json.dumps(
                    {
                        "errorCode": (result.get("error") or {}).get("code"),
                        "errorMessage": (result.get("error") or {}).get("message"),
                    }
                ),
                params_json=json.dumps(kwargs),
                updated_at=datetime.utcnow(),
            )
            db.merge(job)
            db.commit()
    return {
        "jobId": str(result.get("jobId") or kwargs.get("take_id") or ""),
        "status": "completed" if result.get("ok") else "failed",
        "audioAssetId": audio_asset_id,
        "durationMs": duration_ms,
        "errorCode": (result.get("error") or {}).get("code"),
        "errorMessage": (result.get("error") or {}).get("message"),
        "providerVersion": status.get("providerVersion"),
        "modelRevision": status.get("modelRevision"),
        "outputPath": output_path,
    }
