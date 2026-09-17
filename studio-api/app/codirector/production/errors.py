"""Typed production-orchestration errors. Never swallow into a fake 0/1 job."""

from __future__ import annotations


class ProductionError(Exception):
    code = "PRODUCTION_ERROR"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class SceneIntentParseError(ProductionError):
    code = "SCENE_INTENT_PARSE_FAILED"


class ReferenceResolutionError(ProductionError):
    code = "REFERENCE_RESOLUTION_FAILED"


class GeneratorValidationError(ProductionError):
    code = "GENERATOR_VALIDATION_FAILED"


class PromptCompileError(ProductionError):
    code = "PROMPT_COMPILE_FAILED"


class TimelineShotCreationError(ProductionError):
    code = "TIMELINE_SHOT_CREATE_FAILED"


class GenerationSubmissionError(ProductionError):
    code = "GENERATION_SUBMISSION_FAILED"
