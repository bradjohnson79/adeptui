
"""M4.12 Co-Director avatar presentation intelligence tools.

TEMPORARILY RETIRED from current Adept UI production.
InfiniteTalk / Wan unsuitable for current production direction.
Future: revisit as cloud for Adept UI v1.2. Tools stay registered but refuse execution.
"""

from __future__ import annotations

from typing import Any

AVATAR_STUDIO_RETIRED = True
AVATAR_STUDIO_RETIRED_MESSAGE = (
    "Avatar Studio is not part of the current Adept UI production build. "
    "It has been temporarily retired (InfiniteTalk / Wan are not in the current production direction). "
    "Existing Avatar Library outputs remain available. Voice Creator remains available. "
    "Future direction: cloud Avatar for Adept UI v1.2 (no delivery date)."
)


def _retired_result(**extra: Any) -> dict[str, Any]:
    payload = {
        "_summary": AVATAR_STUDIO_RETIRED_MESSAGE,
        "_status": "unavailable",
        "_retired": True,
        "available": False,
        "message": AVATAR_STUDIO_RETIRED_MESSAGE,
    }
    payload.update(extra)
    return payload


def _refuse(*_args, **_kwargs):
    return _retired_result()


inspect = _refuse
get_provider_status = _refuse
get_script_context = _refuse
get_voice_context = _refuse
get_job = _refuse
get_section = _refuse
compare_sections = _refuse
check_continuity = _refuse
preview_create_plan = _refuse
apply_create_plan = _refuse
preview_create_job = _refuse
apply_create_job = _refuse
preview_adjust_section = _refuse
apply_adjust_section = _refuse
preview_request_retake = _refuse
apply_request_retake = _refuse
preview_repair_lipsync = _refuse
apply_repair_lipsync = _refuse
preview_replace_voice = _refuse
apply_replace_voice = _refuse
preview_assemble = _refuse
apply_assemble = _refuse
preview_prepare_timeline = _refuse
apply_prepare_timeline = _refuse
