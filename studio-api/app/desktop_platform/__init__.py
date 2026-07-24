"""Platform-neutral desktop boundaries for future host integrations."""

from .contracts import (
    ClipboardService,
    DialogService,
    FileSystem,
    NotificationService,
    OperatingSystem,
    OSIntegrationService,
    SecretsStore,
    SettingsStore,
    TemporaryFileService,
    WindowService,
)

__all__ = [
    "ClipboardService",
    "DialogService",
    "FileSystem",
    "NotificationService",
    "OperatingSystem",
    "OSIntegrationService",
    "SecretsStore",
    "SettingsStore",
    "TemporaryFileService",
    "WindowService",
]
