from .direct_http import DirectHttpDownloadExecutor
from .fixture import FixtureDownloadExecutor
from .local_copy import LocalCopyExecutor

__all__ = [
    "DirectHttpDownloadExecutor",
    "FixtureDownloadExecutor",
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
    }
    return mapping.get(provider_id) or DirectHttpDownloadExecutor()
