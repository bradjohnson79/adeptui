"""Source Manager providers."""

from .direct_http import DirectHttpProvider
from .existing_install import ExistingInstallProvider
from .fixture import FixtureProvider
from .github_api import GitHubApiProvider
from .github_cli import GitHubCliProvider
from .huggingface_cli import HuggingFaceCliProvider
from .local_folder import LocalFolderProvider

__all__ = [
    "DirectHttpProvider",
    "ExistingInstallProvider",
    "FixtureProvider",
    "GitHubApiProvider",
    "GitHubCliProvider",
    "HuggingFaceCliProvider",
    "LocalFolderProvider",
]
