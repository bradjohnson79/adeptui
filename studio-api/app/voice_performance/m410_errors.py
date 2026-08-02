"""Typed M4.10 Voice Performance error contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import HTTPException


class M410ErrorCode(str, Enum):
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"
    TAKE_NOT_FOUND = "TAKE_NOT_FOUND"
    SCENE_NOT_FOUND = "SCENE_NOT_FOUND"
    SCRIPT_DOCUMENT_NOT_FOUND = "SCRIPT_DOCUMENT_NOT_FOUND"
    SCRIPT_ELEMENT_NOT_FOUND = "SCRIPT_ELEMENT_NOT_FOUND"
    VOICE_IDENTITY_REQUIRED = "VOICE_IDENTITY_REQUIRED"
    VOICE_IDENTITY_NOT_APPROVED = "VOICE_IDENTITY_NOT_APPROVED"
    EMOTION_VECTOR_INVALID = "EMOTION_VECTOR_INVALID"
    INVALID_DIRECTION_MODE = "INVALID_DIRECTION_MODE"
    TAKE_NOT_READY = "TAKE_NOT_READY"
    APPROVED_TAKE_REQUIRED = "APPROVED_TAKE_REQUIRED"
    CONFIRM_REQUIRED = "CONFIRM_REQUIRED"
    TIMELINE_REPLACE_CONFIRM_REQUIRED = "TIMELINE_REPLACE_CONFIRM_REQUIRED"
    RUNTIME_NOT_READY = "RUNTIME_NOT_READY"


ERROR_DETAILS: dict[M410ErrorCode, dict[str, Any]] = {
    M410ErrorCode.PROJECT_NOT_FOUND: {
        "status": 404,
        "explanation": "The requested project does not exist.",
        "recovery": "Confirm the projectId and retry.",
    },
    M410ErrorCode.RECORD_NOT_FOUND: {
        "status": 404,
        "explanation": "The voice performance record could not be found.",
        "recovery": "Refresh the record list and retry with a valid record id.",
    },
    M410ErrorCode.TAKE_NOT_FOUND: {
        "status": 404,
        "explanation": "The requested take does not exist on this record.",
        "recovery": "Reload takes for the record and select a valid take.",
    },
    M410ErrorCode.SCENE_NOT_FOUND: {
        "status": 404,
        "explanation": "The target scene could not be found.",
        "recovery": "Confirm the sceneId belongs to this project before placing audio.",
    },
    M410ErrorCode.SCRIPT_DOCUMENT_NOT_FOUND: {
        "status": 404,
        "explanation": "The referenced script document does not exist.",
        "recovery": "Open the script document again and retry with a valid document id.",
    },
    M410ErrorCode.SCRIPT_ELEMENT_NOT_FOUND: {
        "status": 404,
        "explanation": "The referenced script element could not be found in the document.",
        "recovery": "Refresh the script document and choose a valid line or element id.",
    },
    M410ErrorCode.VOICE_IDENTITY_REQUIRED: {
        "status": 400,
        "explanation": "An approved voice identity is required before takes can be generated.",
        "recovery": "Approve a voice identity for the character, then retry.",
    },
    M410ErrorCode.VOICE_IDENTITY_NOT_APPROVED: {
        "status": 409,
        "explanation": "The selected voice identity exists but is not approved.",
        "recovery": "Approve the voice identity or choose a different approved voice.",
    },
    M410ErrorCode.EMOTION_VECTOR_INVALID: {
        "status": 400,
        "explanation": "The emotion vector is not compatible with the supported IndexTTS2 contract.",
        "recovery": "Use only supported keys and non-negative numeric values.",
    },
    M410ErrorCode.INVALID_DIRECTION_MODE: {
        "status": 400,
        "explanation": "Direction mode must be either codirector or manual.",
        "recovery": "Retry with a supported directionMode value.",
    },
    M410ErrorCode.TAKE_NOT_READY: {
        "status": 409,
        "explanation": "The selected take is not in a state that can be approved or used yet.",
        "recovery": "Wait for generation to finish or select a completed take.",
    },
    M410ErrorCode.APPROVED_TAKE_REQUIRED: {
        "status": 409,
        "explanation": "This action needs an approved primary take.",
        "recovery": "Approve one completed take for the record, then retry.",
    },
    M410ErrorCode.CONFIRM_REQUIRED: {
        "status": 409,
        "explanation": "This action requires explicit confirmation before mutating existing state.",
        "recovery": "Retry with confirm=true after reviewing the payload.",
    },
    M410ErrorCode.TIMELINE_REPLACE_CONFIRM_REQUIRED: {
        "status": 409,
        "explanation": "Timeline placement would replace existing dialogue clips.",
        "recovery": "Retry with confirmReplace=true if replacement is intended.",
    },
    M410ErrorCode.RUNTIME_NOT_READY: {
        "status": 409,
        "explanation": "The local IndexTTS2 runtime is not ready.",
        "recovery": "Install or verify the runtime, then retry generation.",
    },
}


def explain_error(code: M410ErrorCode | str) -> str:
    try:
        return ERROR_DETAILS[M410ErrorCode(code)]["explanation"]
    except Exception:
        return "Unknown voice performance error."


def recovery_action(code: M410ErrorCode | str) -> str:
    try:
        return ERROR_DETAILS[M410ErrorCode(code)]["recovery"]
    except Exception:
        return "Review the request and retry."


def error_payload(code: M410ErrorCode | str, message: str | None = None, **extra: Any) -> dict[str, Any]:
    enum_code = M410ErrorCode(code)
    detail = ERROR_DETAILS[enum_code]
    payload = {
        "code": enum_code.value,
        "message": message or detail["explanation"],
        "explanation": detail["explanation"],
        "recovery": detail["recovery"],
    }
    payload.update(extra)
    return payload


def raise_http_error(
    code: M410ErrorCode | str,
    message: str | None = None,
    *,
    status_code: int | None = None,
    **extra: Any,
) -> HTTPException:
    enum_code = M410ErrorCode(code)
    status = int(status_code or ERROR_DETAILS[enum_code]["status"])
    return HTTPException(status_code=status, detail=error_payload(enum_code, message, **extra))
