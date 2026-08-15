"""Image Core error codes. Translate in product UI — never leak Comfy tracebacks."""

from __future__ import annotations


UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
MODEL_NOT_INSTALLED = "MODEL_NOT_INSTALLED"
RUNTIME_OFFLINE = "RUNTIME_OFFLINE"
PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
NO_IMAGE_RESULT = "NO_IMAGE_RESULT"
OUTPUT_REJECTED = "OUTPUT_REJECTED"
WORKFLOW_FAILED = "WORKFLOW_FAILED"
RATE_LIMITED = "RATE_LIMITED"


class ImageCoreError(Exception):
    def __init__(self, code: str, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}
