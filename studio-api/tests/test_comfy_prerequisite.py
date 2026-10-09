"""ComfyUI is detected and checked. Adept UI does not install it."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.setup.comfy_prerequisite import (
    OFFICIAL_COMFY_DOWNLOAD_URL,
    connect_existing_comfy,
    rescan_comfy,
)
from app.setup.installation_profile import required_ids_for, save_installation_profile
from app.setup.state import load_state


class _Verification:
    def __init__(self, healthy: bool, issue_code: str | None = None) -> None:
        self.healthy = healthy
        self.issue_code = issue_code
        self.summary = "running" if healthy else "not running"
        self.path = None


@pytest.fixture()
def setup_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings
    from app.setup import status as setup_status

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    setup_status._STATUS_CACHE = None
    return tmp_path


def _patch_health(monkeypatch: pytest.MonkeyPatch, healthy: bool) -> None:
    verification = _Verification(healthy, None if healthy else "offline")
    monkeypatch.setattr("app.setup.diagnostics.invalidate_verify_cache", lambda component_id: None)
    monkeypatch.setattr("app.setup.status.invalidate_status_cache", lambda: None)
    monkeypatch.setattr("app.setup.diagnostics.verify_component", lambda component_id: verification)


def test_connecting_an_existing_install_does_not_change_its_files(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = setup_data_dir / "ComfyUI"
    folder.mkdir()
    main = folder / "main.py"
    main.write_bytes(b"print('comfy')\n")
    _patch_health(monkeypatch, healthy=False)

    result = connect_existing_comfy(str(folder))

    assert main.read_bytes() == b"print('comfy')\n"
    assert load_state()["comfy_install_root"] == str(folder.resolve())
    assert result["installed"] is True
    assert result["healthy"] is False
    assert result["downloadUrl"] == OFFICIAL_COMFY_DOWNLOAD_URL
    assert "Launch it" in result["message"]


def test_a_folder_without_comfyui_is_rejected(setup_data_dir: Path) -> None:
    folder = setup_data_dir / "notes"
    folder.mkdir()
    (folder / "readme.txt").write_text("not comfy", encoding="utf-8")
    with pytest.raises(ValueError, match="does not contain ComfyUI"):
        connect_existing_comfy(str(folder))
    assert "comfy_install_root" not in load_state()


def test_a_url_is_not_a_comfy_install(setup_data_dir: Path) -> None:
    with pytest.raises(ValueError, match="folder"):
        connect_existing_comfy("http://127.0.0.1:8188")


def test_rescan_reports_a_running_engine_without_writing_a_job(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_health(monkeypatch, healthy=True)
    result = rescan_comfy()
    assert result["healthy"] is True
    assert result["message"] == "ComfyUI is running."
    assert not (setup_data_dir / "setup_state.json").exists()


def test_rescan_after_a_saved_folder_says_launch_it(
    setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = setup_data_dir / "ComfyUI"
    folder.mkdir()
    (folder / "main.py").write_text("print(1)\n", encoding="utf-8")
    _patch_health(monkeypatch, healthy=False)
    connect_existing_comfy(str(folder))
    result = rescan_comfy()
    assert result["installed"] is True
    assert result["healthy"] is False
    assert "not running" in result["message"]


def test_api_only_does_not_require_comfyui(setup_data_dir: Path) -> None:
    save_installation_profile("api", providers=["fal"])
    assert "comfyui" not in required_ids_for("api", load_state())


def test_hybrid_without_local_models_does_not_require_comfyui(setup_data_dir: Path) -> None:
    save_installation_profile("hybrid", selected_models=[], providers=["fal"])
    assert "comfyui" not in required_ids_for("hybrid", load_state())


def test_hybrid_with_a_local_model_requires_comfyui(setup_data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.setup.first_run import assess_first_run

    save_installation_profile("hybrid", selected_models=["zimage_models"], providers=["fal"])
    assert "comfyui" in required_ids_for("hybrid", load_state())
    monkeypatch.setattr(
        "app.setup.installation_profile.verified_providers",
        lambda: [{"id": "fal", "name": "fal.ai"}],
    )
    report = assess_first_run(
        [
            {"id": "python", "name": "Python", "status": "ready"},
            {"id": "ffmpeg", "name": "FFmpeg", "status": "ready"},
            {"id": "comfyui", "name": "ComfyUI", "status": "not_installed"},
            {"id": "zimage_models", "name": "Z-Image", "status": "ready"},
        ],
        fetch_nodes=False,
    )
    assert report["ready"] is False
    assert any(item["id"] == "comfyui" for item in report["essentialBlockers"])
    assert report["connectedProviders"] == [{"id": "fal", "name": "fal.ai"}]
    assert load_state()["selected_providers"] == ["fal"]


def test_local_profile_stays_incomplete_until_comfy_is_ready(setup_data_dir: Path) -> None:
    from app.setup.first_run import assess_first_run

    save_installation_profile("local")
    report = assess_first_run(
        [
            {"id": "python", "name": "Python", "status": "ready"},
            {"id": "ffmpeg", "name": "FFmpeg", "status": "ready"},
            {"id": "comfyui", "name": "ComfyUI", "status": "not_installed"},
            {"id": "zimage_models", "name": "Z-Image", "status": "ready"},
            {"id": "ltx_2_5_checkpoint", "name": "LTX", "status": "ready"},
            {"id": "ltx_2_5_text_encoder", "name": "LTX text", "status": "ready"},
            {"id": "ltx_2_5_video_vae", "name": "LTX vae", "status": "ready"},
        ],
        fetch_nodes=False,
    )
    assert report["ready"] is False
    assert any(item["id"] == "comfyui" for item in report["essentialBlockers"])


def test_switching_from_api_to_local_keeps_the_profile_record(setup_data_dir: Path) -> None:
    save_installation_profile("api", providers=["fal"])
    save_installation_profile("local")
    state = load_state()
    assert state["installation_profile"] == "local"
    assert "comfyui" in required_ids_for("local", state)
