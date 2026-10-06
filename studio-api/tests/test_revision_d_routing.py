"""V-JEPA enqueue must never fall through to Hunyuan."""

from inspect import getsource

from app.source_manager.downloads.executors.huggingface_snapshot import HuggingFaceSnapshotExecutor
from app.source_manager.install_jobs.service import create_or_resume_install


def test_hf_executor_supports_vjepa():
    executor = HuggingFaceSnapshotExecutor()
    src = getsource(executor.execute)
    assert "vjepa2_world_intelligence" in getsource(HuggingFaceSnapshotExecutor) or "_WORLD_INTELLIGENCE" in getsource(
        HuggingFaceSnapshotExecutor
    )
    assert "_execute_world_intelligence" in getsource(HuggingFaceSnapshotExecutor)


def test_create_or_resume_routes_vjepa_before_hunyuan():
    text = getsource(create_or_resume_install)
    assert "vjepa2_world_intelligence" in text
    assert text.index("_enqueue_world_intelligence") < text.index("_enqueue_hunyuan")
