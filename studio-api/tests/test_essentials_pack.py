"""Essentials Pack registry and V-JEPA install routing."""

from app.setup.catalog import BY_ID, get_component
from app.setup.essentials_pack import ESSENTIAL_IDS, RECOMMENDED_IDS, pack_status, preflight_install
from app.source_manager.downloads.executors.huggingface_snapshot import HuggingFaceSnapshotExecutor


def test_essentials_ids_are_catalogued():
    for component_id in (*ESSENTIAL_IDS, *RECOMMENDED_IDS):
        assert component_id in BY_ID
        assert get_component(component_id).required is False or component_id == "videochat3_4b"


def test_pack_status_does_not_block_generation():
    status = pack_status()
    assert status["id"] == "adept_ui_essentials"
    assert status["channel"] == "local_essentials"
    assert status["generationBlockedByPack"] is False
    assert status["essentialTotal"] == 5
    names = {row["id"] for row in status["components"]}
    assert "videochat3_4b" in names
    assert "sam21_hiera_tiny" in names
    assert "moge2_geometry" in names
    assert "vggt_1b_commercial" in names
    assert "timelens" not in names
    assert "vggt" not in names


def test_spatial_group_tracks_installable_essentials_not_gated_vggt():
    status = pack_status()
    spatial = next(group for group in status["groups"] if group["id"] == "spatial_intelligence")
    moge = next(row for row in status["components"] if row["id"] == "moge2_geometry")
    vggt = next(row for row in status["components"] if row["id"] == "vggt_1b_commercial")
    assert vggt["accessGated"] is True
    assert spatial["installed"] is bool(moge["installed"])


def test_preflight_reports_missing_without_starting():
    preflight = preflight_install(include_recommended=False)
    assert "modelsMissing" in preflight
    assert "requiredGb" in preflight
    assert "availableGb" in preflight


def test_vjepa_is_not_hunyuan_in_executor():
    executor = HuggingFaceSnapshotExecutor()
    caps = executor.get_capabilities({"componentId": "vjepa2_world_intelligence"})
    assert caps.can_cancel is True


def test_enqueue_world_intelligence_function_exists():
    from app.source_manager.install_jobs import service as jobs

    assert hasattr(jobs, "_enqueue_world_intelligence")
    src = jobs.create_or_resume_install.__code__.co_consts
    # Routing is in the function body; import the source text.
    from inspect import getsource

    text = getsource(jobs.create_or_resume_install)
    assert "vjepa2_world_intelligence" in text
    assert text.index("vjepa2_world_intelligence") < text.index("_enqueue_hunyuan")
