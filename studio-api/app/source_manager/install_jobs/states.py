from __future__ import annotations

from enum import Enum


class InstallState(str, Enum):
    NOT_INSTALLED = "not_installed"
    SOURCE_REQUIRED = "source_required"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    QUEUED = "queued"
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    VERIFYING_DOWNLOAD = "verifying_download"
    INSTALLING = "installing"
    CONFIGURING = "configuring"
    VERIFYING_INSTALL = "verifying_install"
    READY = "ready"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    REPAIR_REQUIRED = "repair_required"
    FAILED = "failed"
