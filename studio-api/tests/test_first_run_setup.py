"""First-run flag follows the existing image/video baseline. Optional models never set it."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from app.setup.first_run import (
    INVARIANT_LOG,
    MIGRATION_LOG,
    FirstRunNotReady,
    assess_first_run,
    complete_first_run,
    resolve_first_run,
)


@pytest.fixture()
def setup_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.config import settings
    from app.setup import status as setup_status

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    setup_status._STATUS_CACHE = None
    return tmp_path


def _nodes() -> set[str]:
    from app.workflows.registry import DEFAULT_WORKFLOW_REGISTRY

    names: set[str] = set()
    for key in ("image.txt2img", "ltx_25.t2v"):
        meta = DEFAULT_WORKFLOW_REGISTRY.get(key)
        names.update(meta.compatibility.required_node_types)
    return names


def _components(**overrides: str) -> list[dict]:
    ids = (
        "python",
        "ffmpeg",
        "comfyui",
        "zimage_models",
        "ltx_2_5_checkpoint",
        "ltx_2_5_text_encoder",
        "ltx_2_5_video_vae",
    )
    rows = []
    for component_id in ids:
        rows.append(
            {
                "id": component_id,
                "name": component_id,
                "required": component_id in {"python", "ffmpeg", "comfyui"},
                "status": overrides.get(component_id, "ready"),
                "download_bytes": 100,
                "installed_bytes": 200,
            }
        )
    optional = overrides.get("optional")
    if optional is not None:
        rows.append(
            {
                "id": "minimax_h3_base_optimized",
                "name": "MiniMax H3",
                "required": False,
                "status": optional,
            }
        )
    return rows


def _flag(setup_data_dir: Path):
    path = setup_data_dir / "setup_state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("first_run_setup_complete", None)


def _resolve(components: list[dict]) -> bool:
    return resolve_first_run(components, node_types=_nodes(), fetch_nodes=False)


def test_system_essentials_alone_do_not_complete(setup_data_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        assert _resolve(_components(zimage_models="not_installed")) is False
    assert _flag(setup_data_dir) is False
    assert MIGRATION_LOG not in caplog.text
    report = assess_first_run(_components(zimage_models="not_installed"), node_types=_nodes(), fetch_nodes=False)
    assert report["essentialBlockerCount"] > 0
    assert report["baselineImageWorkflow"] == "blocked"


def test_full_baseline_saves_the_flag_and_optional_absence_does_not_block(
    setup_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    assert _resolve(_components(ffmpeg="not_installed")) is False
    with caplog.at_level(logging.INFO):
        assert complete_first_run(_components(optional="not_installed"), node_types=_nodes(), fetch_nodes=False) is True
    assert _flag(setup_data_dir) is True
    assert MIGRATION_LOG not in caplog.text
    before = (setup_data_dir / "setup_state.json").read_text(encoding="utf-8")
    assert _resolve(_components(optional="not_installed")) is True
    assert complete_first_run(_components(optional="not_installed"), node_types=_nodes(), fetch_nodes=False) is True
    assert (setup_data_dir / "setup_state.json").read_text(encoding="utf-8") == before
    report = assess_first_run(_components(optional="not_installed"), node_types=_nodes(), fetch_nodes=False)
    assert report["essentialBlockerCount"] == 0
    assert report["baselineImageWorkflow"] == "ready"
    assert report["baselineVideoWorkflow"] == "ready"
    assert report["optionalAbsentCount"] == 1


def test_existing_install_migrates_once_when_the_baseline_is_ready(
    setup_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (setup_data_dir / "setup_state.json").write_text(
        json.dumps({"schema_version": 3, "components": {}}),
        encoding="utf-8",
    )
    with caplog.at_level(logging.INFO):
        assert _resolve(_components(optional="not_installed")) is True
        assert _resolve(_components(optional="not_installed")) is True
    assert _flag(setup_data_dir) is True
    assert caplog.text.count(MIGRATION_LOG) == 1


def test_true_flag_clears_when_an_essential_blocker_returns(
    setup_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    assert complete_first_run(_components(), node_types=_nodes(), fetch_nodes=False) is True
    with caplog.at_level(logging.INFO):
        assert _resolve(_components(ltx_2_5_video_vae="error")) is False
    assert _flag(setup_data_dir) is False
    assert INVARIANT_LOG in caplog.text


def test_complete_refuses_until_the_baseline_is_ready(setup_data_dir: Path) -> None:
    _resolve(_components(ffmpeg="not_installed"))
    with pytest.raises(FirstRunNotReady):
        complete_first_run(_components(ffmpeg="error"), node_types=_nodes(), fetch_nodes=False)
    assert _flag(setup_data_dir) is False


def test_missing_nodes_keep_the_video_workflow_blocked(setup_data_dir: Path) -> None:
    report = assess_first_run(_components(), node_types=set(), fetch_nodes=False)
    assert report["baselineVideoWorkflow"] == "blocked"
    assert report["essentialBlockerCount"] > 0
    assert resolve_first_run(_components(), node_types=set(), fetch_nodes=False) is False
    assert _flag(setup_data_dir) is False


def test_unreadable_record_is_not_treated_as_a_new_first_run(setup_data_dir: Path) -> None:
    path = setup_data_dir / "setup_state.json"
    path.write_text("{not-json", encoding="utf-8")
    assert resolve_first_run(_components(python="not_installed"), fetch_nodes=False) is True
    assert complete_first_run(_components(python="not_installed"), fetch_nodes=False) is True
    assert path.read_text(encoding="utf-8") == "{not-json"


def test_first_run_module_does_not_reference_the_h3_license_manager() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("app", "setup", "first_run.py").read_text(encoding="utf-8")
    assert "model_license" not in source
    assert "minimax" not in source.lower()
