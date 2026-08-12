from __future__ import annotations

from fastapi import HTTPException


class VoiceEnvironmentError(Exception):
    def __init__(self, code: str, message: str, *, details: dict | None = None, status_code: int = 400):
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(message)


def http_error(exc: VoiceEnvironmentError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "creatorMessage": exc.message,
            "details": exc.details,
            "retryable": exc.code
            in {
                "VOICE_ENVIRONMENT_PREVIEW_FAILED",
                "VOICE_ENVIRONMENT_RENDER_FAILED",
                "VOICE_ENVIRONMENT_RUNTIME_NOT_READY",
            },
            "repairAction": "Open Setup"
            if "RUNTIME" in exc.code or "NOT_READY" in exc.code
            else None,
            "affectedStage": "Voice Environment",
        },
    )
