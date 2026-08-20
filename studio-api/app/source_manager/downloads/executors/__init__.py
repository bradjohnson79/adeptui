from .direct_http import DirectHttpDownloadExecutor
from .fixture import FixtureDownloadExecutor
from .huggingface_snapshot import HuggingFaceSnapshotExecutor
from .local_copy import LocalCopyExecutor
from .stills_perception import StillsPerceptionExecutor

__all__ = [
    "DirectHttpDownloadExecutor",
    "FixtureDownloadExecutor",
    "HuggingFaceSnapshotExecutor",
    "LocalCopyExecutor",
]


def get_executor(provider_id: str):
    mapping = {
        "fixture": FixtureDownloadExecutor(),
        "direct_http": DirectHttpDownloadExecutor(),
        "github_api": DirectHttpDownloadExecutor(),
        "local_folder": LocalCopyExecutor(),
        "existing_install": LocalCopyExecutor(),
        # CLI executors: fall back to fixture/direct until dedicated adapters mature
        "github_cli": DirectHttpDownloadExecutor(),
        "huggingface_cli": DirectHttpDownloadExecutor(),
        "huggingface_snapshot": HuggingFaceSnapshotExecutor(),
        "huggingface_hub": HuggingFaceSnapshotExecutor(),
        "stills_perception_hf": StillsPerceptionExecutor(),
    }
    return mapping.get(provider_id) or DirectHttpDownloadExecutor()
