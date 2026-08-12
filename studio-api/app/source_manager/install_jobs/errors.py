from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InstallJobErrorCode(str, Enum):
    INSTALL_SOURCE_MISSING = "INSTALL_SOURCE_MISSING"
    INSTALL_SOURCE_INVALID = "INSTALL_SOURCE_INVALID"
    INSTALL_SOURCE_UNREACHABLE = "INSTALL_SOURCE_UNREACHABLE"
    INSTALL_PERMISSION_DENIED = "INSTALL_PERMISSION_DENIED"
    INSTALL_DISK_SPACE_INSUFFICIENT = "INSTALL_DISK_SPACE_INSUFFICIENT"
    INSTALL_DOWNLOAD_FAILED = "INSTALL_DOWNLOAD_FAILED"
    INSTALL_DOWNLOAD_INTERRUPTED = "INSTALL_DOWNLOAD_INTERRUPTED"
    INSTALL_CHECKSUM_MISMATCH = "INSTALL_CHECKSUM_MISMATCH"
    INSTALL_FILE_MISSING = "INSTALL_FILE_MISSING"
    INSTALL_ARCHIVE_CORRUPT = "INSTALL_ARCHIVE_CORRUPT"
    INSTALL_DEPENDENCY_FAILED = "INSTALL_DEPENDENCY_FAILED"
    INSTALL_PYTHON_VERSION_UNSUPPORTED = "INSTALL_PYTHON_VERSION_UNSUPPORTED"
    INSTALL_CUDA_UNAVAILABLE = "INSTALL_CUDA_UNAVAILABLE"
    INSTALL_GPU_INCOMPATIBLE = "INSTALL_GPU_INCOMPATIBLE"
    INSTALL_EXTENSION_MISSING = "INSTALL_EXTENSION_MISSING"
    INSTALL_EXTENSION_VERSION_MISMATCH = "INSTALL_EXTENSION_VERSION_MISMATCH"
    INSTALL_RUNTIME_START_FAILED = "INSTALL_RUNTIME_START_FAILED"
    INSTALL_HEALTH_CHECK_FAILED = "INSTALL_HEALTH_CHECK_FAILED"
    INSTALL_CANCELLED = "INSTALL_CANCELLED"
    INSTALL_UNKNOWN_FAILURE = "INSTALL_UNKNOWN_FAILURE"
    INSTALL_CONFIRM_REQUIRED = "INSTALL_CONFIRM_REQUIRED"
    INSTALL_CONFIRM_DOWNLOAD_MODELS_REQUIRED = "INSTALL_CONFIRM_DOWNLOAD_MODELS_REQUIRED"
    INSTALL_UNSUPPORTED_ACTION = "INSTALL_UNSUPPORTED_ACTION"
    INSTALL_NOT_FOUND = "INSTALL_NOT_FOUND"


# Legacy attribute aliases for older call sites (InstallJobErrorCode.DISK_FULL, etc.).
_LEGACY_ATTRS = {
    "CONFIRM_REQUIRED": "INSTALL_CONFIRM_REQUIRED",
    "CONFIRM_DOWNLOAD_MODELS_REQUIRED": "INSTALL_CONFIRM_DOWNLOAD_MODELS_REQUIRED",
    "SOURCE_REQUIRED": "INSTALL_SOURCE_MISSING",
    "SOURCE_INVALID": "INSTALL_SOURCE_INVALID",
    "SOURCE_AUTH_REQUIRED": "INSTALL_SOURCE_UNREACHABLE",
    "SOURCE_MISSING": "INSTALL_SOURCE_MISSING",
    "DISK_FULL": "INSTALL_DISK_SPACE_INSUFFICIENT",
    "DESTINATION_UNWRITABLE": "INSTALL_PERMISSION_DENIED",
    "VALIDATION_FAILED": "INSTALL_HEALTH_CHECK_FAILED",
    "DOWNLOAD_FAILED": "INSTALL_DOWNLOAD_FAILED",
    "INSTALL_FAILED": "INSTALL_UNKNOWN_FAILURE",
    "VERIFICATION_FAILED": "INSTALL_HEALTH_CHECK_FAILED",
    "CANCELLED": "INSTALL_CANCELLED",
    "INTERRUPTED": "INSTALL_DOWNLOAD_INTERRUPTED",
    "PROVIDER_ERROR": "INSTALL_DOWNLOAD_FAILED",
    "DEPENDENCY_MISSING": "INSTALL_DEPENDENCY_FAILED",
    "UNSUPPORTED_ACTION": "INSTALL_UNSUPPORTED_ACTION",
    "NOT_FOUND": "INSTALL_NOT_FOUND",
    "UNKNOWN": "INSTALL_UNKNOWN_FAILURE",
}


# Bind legacy names onto the enum class for `InstallJobErrorCode.DISK_FULL` style access.
for _legacy_name, _public_name in _LEGACY_ATTRS.items():
    if not hasattr(InstallJobErrorCode, _legacy_name):
        setattr(InstallJobErrorCode, _legacy_name, InstallJobErrorCode(_public_name))


_CODE_TITLES: dict[str, str] = {
    "INSTALL_SOURCE_MISSING": "Source required",
    "INSTALL_SOURCE_INVALID": "Source invalid",
    "INSTALL_SOURCE_UNREACHABLE": "Source unreachable",
    "INSTALL_PERMISSION_DENIED": "Permission denied",
    "INSTALL_DISK_SPACE_INSUFFICIENT": "Not enough disk space",
    "INSTALL_DOWNLOAD_FAILED": "Download failed",
    "INSTALL_DOWNLOAD_INTERRUPTED": "Download interrupted",
    "INSTALL_CHECKSUM_MISMATCH": "File verification failed",
    "INSTALL_FILE_MISSING": "Required files missing",
    "INSTALL_ARCHIVE_CORRUPT": "Archive corrupt",
    "INSTALL_DEPENDENCY_FAILED": "Dependency install failed",
    "INSTALL_PYTHON_VERSION_UNSUPPORTED": "Python version unsupported",
    "INSTALL_CUDA_UNAVAILABLE": "CUDA unavailable",
    "INSTALL_GPU_INCOMPATIBLE": "GPU incompatible",
    "INSTALL_EXTENSION_MISSING": "Extension missing",
    "INSTALL_EXTENSION_VERSION_MISMATCH": "Extension version mismatch",
    "INSTALL_RUNTIME_START_FAILED": "Runtime failed to start",
    "INSTALL_HEALTH_CHECK_FAILED": "Health check failed",
    "INSTALL_CANCELLED": "Installation cancelled",
    "INSTALL_UNKNOWN_FAILURE": "Installation failed",
    "INSTALL_CONFIRM_REQUIRED": "Confirmation required",
    "INSTALL_CONFIRM_DOWNLOAD_MODELS_REQUIRED": "Model download confirmation required",
    "INSTALL_UNSUPPORTED_ACTION": "Action not supported",
    "INSTALL_NOT_FOUND": "Install job not found",
}


_LEGACY_TO_PUBLIC: dict[str, InstallJobErrorCode] = {
    "confirm_required": InstallJobErrorCode.INSTALL_CONFIRM_REQUIRED,
    "confirm_download_models_required": InstallJobErrorCode.INSTALL_CONFIRM_DOWNLOAD_MODELS_REQUIRED,
    "source_required": InstallJobErrorCode.INSTALL_SOURCE_MISSING,
    "source_invalid": InstallJobErrorCode.INSTALL_SOURCE_INVALID,
    "source_auth_required": InstallJobErrorCode.INSTALL_SOURCE_UNREACHABLE,
    "source_missing": InstallJobErrorCode.INSTALL_SOURCE_MISSING,
    "disk_full": InstallJobErrorCode.INSTALL_DISK_SPACE_INSUFFICIENT,
    "destination_unwritable": InstallJobErrorCode.INSTALL_PERMISSION_DENIED,
    "permission_denied": InstallJobErrorCode.INSTALL_PERMISSION_DENIED,
    "validation_failed": InstallJobErrorCode.INSTALL_HEALTH_CHECK_FAILED,
    "download_failed": InstallJobErrorCode.INSTALL_DOWNLOAD_FAILED,
    "install_failed": InstallJobErrorCode.INSTALL_UNKNOWN_FAILURE,
    "verification_failed": InstallJobErrorCode.INSTALL_HEALTH_CHECK_FAILED,
    "cancelled": InstallJobErrorCode.INSTALL_CANCELLED,
    "interrupted": InstallJobErrorCode.INSTALL_DOWNLOAD_INTERRUPTED,
    "process_crashed": InstallJobErrorCode.INSTALL_DOWNLOAD_INTERRUPTED,
    "provider_error": InstallJobErrorCode.INSTALL_DOWNLOAD_FAILED,
    "dependency_missing": InstallJobErrorCode.INSTALL_DEPENDENCY_FAILED,
    "unsupported_action": InstallJobErrorCode.INSTALL_UNSUPPORTED_ACTION,
    "not_found": InstallJobErrorCode.INSTALL_NOT_FOUND,
    "unknown": InstallJobErrorCode.INSTALL_UNKNOWN_FAILURE,
    "network_unavailable": InstallJobErrorCode.INSTALL_DOWNLOAD_FAILED,
    "authentication_required": InstallJobErrorCode.INSTALL_SOURCE_UNREACHABLE,
    "rate_limited": InstallJobErrorCode.INSTALL_DOWNLOAD_FAILED,
    "artifact_missing": InstallJobErrorCode.INSTALL_FILE_MISSING,
    "source_changed": InstallJobErrorCode.INSTALL_SOURCE_INVALID,
    "checksum_mismatch": InstallJobErrorCode.INSTALL_CHECKSUM_MISMATCH,
    "archive_invalid": InstallJobErrorCode.INSTALL_ARCHIVE_CORRUPT,
    "index_tts2_install_failed": InstallJobErrorCode.INSTALL_HEALTH_CHECK_FAILED,
}


class InstallJobError(BaseModel):
    code: InstallJobErrorCode
    title: str = ""
    user_message: str = Field(default="", alias="userMessage")
    message: str = ""
    technical_message: str | None = Field(default=None, alias="technicalMessage")
    affected_files: list[str] = Field(default_factory=list, alias="affectedFiles")
    affected_dependencies: list[str] = Field(default_factory=list, alias="affectedDependencies")
    retryable: bool = True
    repairable: bool = False
    recoverable: bool = True
    suggested_action: str | None = Field(default=None, alias="suggestedAction")
    recommended_action: str | None = Field(default=None, alias="recommendedAction")
    log_reference: str | None = Field(default=None, alias="logReference")
    phase: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    def model_post_init(self, __context: Any) -> None:
        public = public_code(self.code)
        object.__setattr__(self, "code", public)
        if not self.title:
            object.__setattr__(self, "title", _CODE_TITLES.get(public.value, "Installation issue"))
        user = self.user_message or self.message or self.title
        object.__setattr__(self, "user_message", user)
        object.__setattr__(self, "message", user)
        if self.recommended_action and not self.suggested_action:
            object.__setattr__(self, "suggested_action", self.recommended_action)
        elif self.suggested_action and not self.recommended_action:
            object.__setattr__(self, "recommended_action", self.suggested_action)
        retryable = bool(self.retryable if self.retryable is not None else self.recoverable)
        object.__setattr__(self, "retryable", retryable)
        object.__setattr__(self, "recoverable", retryable)


def public_code(code: InstallJobErrorCode | str | None) -> InstallJobErrorCode:
    if isinstance(code, InstallJobErrorCode):
        return code
    value = str(code or "").strip()
    if not value:
        return InstallJobErrorCode.INSTALL_UNKNOWN_FAILURE
    upper = value.upper()
    if upper.startswith("INSTALL_"):
        try:
            return InstallJobErrorCode(upper)
        except ValueError:
            pass
    lower = value.lower()
    if lower in _LEGACY_TO_PUBLIC:
        return _LEGACY_TO_PUBLIC[lower]
    return InstallJobErrorCode.INSTALL_UNKNOWN_FAILURE


def _coerce_code(raw: str | None) -> InstallJobErrorCode:
    return public_code(raw)


_FAILURE_MAP: dict[str, tuple[InstallJobErrorCode, str | None, bool, bool]] = {
    "network_unavailable": (InstallJobErrorCode.INSTALL_DOWNLOAD_FAILED, "retry_connection", True, True),
    "authentication_required": (InstallJobErrorCode.INSTALL_SOURCE_UNREACHABLE, "sign_in", True, False),
    "permission_denied": (InstallJobErrorCode.INSTALL_PERMISSION_DENIED, "change_destination", True, True),
    "rate_limited": (InstallJobErrorCode.INSTALL_DOWNLOAD_FAILED, "retry_connection", True, False),
    "source_missing": (InstallJobErrorCode.INSTALL_SOURCE_MISSING, "save_source", True, True),
    "artifact_missing": (InstallJobErrorCode.INSTALL_FILE_MISSING, "repair_missing_files", True, True),
    "source_changed": (InstallJobErrorCode.INSTALL_SOURCE_INVALID, "save_source", True, True),
    "checksum_mismatch": (InstallJobErrorCode.INSTALL_CHECKSUM_MISMATCH, "retry_download", True, True),
    "archive_invalid": (InstallJobErrorCode.INSTALL_ARCHIVE_CORRUPT, "retry_download", True, True),
    "disk_full": (InstallJobErrorCode.INSTALL_DISK_SPACE_INSUFFICIENT, "change_destination", True, True),
    "destination_unwritable": (
        InstallJobErrorCode.INSTALL_PERMISSION_DENIED,
        "change_destination",
        True,
        True,
    ),
    "cancelled": (InstallJobErrorCode.INSTALL_CANCELLED, None, True, False),
    "process_crashed": (InstallJobErrorCode.INSTALL_DOWNLOAD_INTERRUPTED, "restart_worker", True, True),
    "provider_error": (InstallJobErrorCode.INSTALL_DOWNLOAD_FAILED, "retry_download", True, True),
    "validation_failed": (InstallJobErrorCode.INSTALL_HEALTH_CHECK_FAILED, "reverify", True, True),
    "unknown": (InstallJobErrorCode.INSTALL_UNKNOWN_FAILURE, "retry_download", True, True),
}


def normalize_failure(failure: dict[str, Any] | None) -> InstallJobError:
    if not isinstance(failure, dict):
        return InstallJobError(
            code=InstallJobErrorCode.INSTALL_UNKNOWN_FAILURE,
            userMessage="Install failed for an unknown reason.",
            message="Install failed for an unknown reason.",
            retryable=True,
            repairable=True,
            recommendedAction="retry_download",
            suggestedAction="retry_download",
        )

    if failure.get("code") or failure.get("message") or failure.get("userMessage"):
        category = str(failure.get("category") or "").strip().lower()
        mapped = _FAILURE_MAP.get(category)
        code = _coerce_code(str(failure.get("code") or failure.get("category") or ""))
        user = str(
            failure.get("userMessage")
            or failure.get("message")
            or _CODE_TITLES.get(code.value, "Install failed.")
        )
        mapped_action = mapped[1] if mapped else None
        mapped_repairable = mapped[3] if mapped else False
        action = (
            failure.get("recommendedAction")
            or failure.get("recommended_action")
            or failure.get("suggestedAction")
            or mapped_action
        )
        return InstallJobError(
            code=code,
            title=str(failure.get("title") or _CODE_TITLES.get(code.value, "Installation issue")),
            userMessage=user,
            message=user,
            technicalMessage=failure.get("technicalMessage") or failure.get("technical_message"),
            affectedFiles=list(failure.get("affectedFiles") or failure.get("affected_files") or []),
            affectedDependencies=list(
                failure.get("affectedDependencies") or failure.get("affected_dependencies") or []
            ),
            retryable=bool(failure.get("retryable", failure.get("recoverable", True))),
            repairable=bool(failure.get("repairable", mapped_repairable)),
            recoverable=bool(failure.get("retryable", failure.get("recoverable", True))),
            phase=failure.get("phase"),
            recommendedAction=action,
            suggestedAction=action,
            logReference=failure.get("logReference") or failure.get("log_reference"),
            details=dict(failure.get("details") or {}),
        )

    category = str(failure.get("category") or "unknown").strip().lower()
    code, action, retryable, repairable = _FAILURE_MAP.get(
        category,
        (InstallJobErrorCode.INSTALL_UNKNOWN_FAILURE, "retry_download", True, True),
    )
    user = str(failure.get("message") or _CODE_TITLES.get(code.value, "Install failed."))
    return InstallJobError(
        code=code,
        title=_CODE_TITLES.get(code.value, "Installation issue"),
        userMessage=user,
        message=user,
        retryable=bool(failure.get("recoverable", retryable)),
        repairable=repairable,
        recoverable=bool(failure.get("recoverable", retryable)),
        phase=failure.get("phase"),
        recommendedAction=failure.get("recommendedAction")
        or failure.get("recommended_action")
        or action,
        suggestedAction=failure.get("suggestedAction")
        or failure.get("recommendedAction")
        or failure.get("recommended_action")
        or action,
        details=dict(failure.get("details") or {}),
    )
