"""H-P1-09…13 Ready contract, path honesty, and GPU snapshot helpers."""

from __future__ import annotations

from pathlib import Path

from app.readiness.contract import (
    READY_REQUIRES_FILESYSTEM_PATH,
    apply_files_ready_gate,
    discover_model_roots,
    is_filesystem_install_path,
)


def test_url_is_not_an_install_path() -> None:
    assert is_filesystem_install_path("http://127.0.0.1:8188") is False
    assert is_filesystem_install_path("https://example.com/models") is False
    assert is_filesystem_install_path("") is False
    assert is_filesystem_install_path(None) is False


def test_filesystem_path_is_an_install_path(tmp_path: Path) -> None:
    assert is_filesystem_install_path(str(tmp_path)) is True
    assert is_filesystem_install_path(r"C:\AdeptFilmWorks\AIVideoStudio\data\models") is True


def test_ready_gate_refuses_url_and_null() -> None:
    assert apply_files_ready_gate("ready", "http://127.0.0.1:8188") == "error"
    assert apply_files_ready_gate("ready", None) == "error"
    assert apply_files_ready_gate("ready", r"C:\models\wan.safetensors") == "ready"
    assert apply_files_ready_gate("ready", None, kind="credential") == "ready"
    assert apply_files_ready_gate("ready", None, kind="local_service") == "ready"
    assert apply_files_ready_gate("ready", None, kind="detect_only") == "ready"
    assert apply_files_ready_gate("ready", None, kind="external_service") == "ready"
    assert apply_files_ready_gate("checking", None) == "checking"


def test_discover_model_roots_labels_machine_specific(tmp_path: Path) -> None:
    from types import SimpleNamespace

    portable = Path(r"C:\AdeptFilmWorks\AIVideoStudio\data")
    settings = SimpleNamespace(
        data_dir=portable,
        comfy_models_dir=Path(r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\models"),
        comfy_input_dir=Path(r"C:\Users\bradj\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input"),
    )
    found = discover_model_roots(settings=settings)
    assert found["machineSpecificCount"] >= 1
    assert any(row["kind"] == "portable" for row in found["roots"])
    assert any(row["kind"] == "machine_specific" for row in found["roots"])
    assert READY_REQUIRES_FILESYSTEM_PATH == "ready_requires_filesystem_path"


def test_gpu_info_uses_nvidia_snapshot(monkeypatch) -> None:
    from app.runtime_manager import service as runtime_service
    from app.runtime_manager.schemas import GpuInfo

    monkeypatch.setattr(
        "runtime_supervisor.gpu_admission.nvidia_snapshot",
        lambda: {
            "ok": True,
            "name": "NVIDIA GeForce RTX 5090",
            "memoryUsedMiB": 12000,
            "memoryTotalMiB": 32607,
            "utilizationPct": 10,
        },
    )
    info = __import__("asyncio").run(runtime_service.get_gpu_info())
    assert isinstance(info, GpuInfo)
    assert info.detected is True
    assert "5090" in (info.name or "")
    assert info.source == "nvidia-smi"
    assert info.vram_total_mib == 32607
    assert info.vram_free_mib == 20607


def test_runtime_view_reports_legacy_windows_task(monkeypatch) -> None:
    from runtime_supervisor.canonical_config import RuntimeConfig
    from runtime_supervisor.service_status import collect_runtime_view
    from runtime_supervisor.windows_task import TaskStatus

    monkeypatch.setattr(
        "runtime_supervisor.service_status.try_load_runtime_config",
        lambda: RuntimeConfig("c", "p", "m"),
    )
    monkeypatch.setattr(
        "runtime_supervisor.service_status.query_task",
        lambda: TaskStatus(name="AdeptRuntimeService", exists=False),
    )
    monkeypatch.setattr(
        "runtime_supervisor.service_status.list_legacy_owners",
        lambda: ["AdeptBetaBackendManager"],
    )
    monkeypatch.setattr(
        "runtime_supervisor.service_status.headless_status",
        lambda: {"healthy": False, "ownership": "down", "owned": False, "pid": None, "queueRunning": 0},
    )
    view = collect_runtime_view()
    assert view["taskRegistered"] is False
    assert view["startWithWindows"] is False
    assert view["windowsStartupPresent"] is True
    assert view["legacyOwners"] == ["AdeptBetaBackendManager"]
