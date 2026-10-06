"""One-shot certification crash points.

Default off. A checkpoint fires only when both the checkpoint name and the
workflow or approval id match, and only once. A restart cannot loop.
"""

from __future__ import annotations

import json
import os

from .journal import crash_consumed, journal_path, mark_crash_consumed

_ARM = "crash_arm.json"


def _armed(checkpoint: str, scope_id: str, requested: str | None) -> bool:
    env_at = os.environ.get("ADEPT_CD_CRASH_AT", "").strip()
    env_scope = os.environ.get("ADEPT_CD_CRASH_SCOPE", "").strip()
    armed = os.environ.get("ADEPT_CD_CRASH_ARMED", "").strip() == "1"
    if requested and requested == checkpoint and armed:
        return True
    if env_at == checkpoint and env_scope == scope_id:
        return True
    arm = journal_path().parent / _ARM
    if not arm.is_file():
        return False
    try:
        payload = json.loads(arm.read_text(encoding="utf-8"))
    except Exception:
        return False
    return payload.get("checkpoint") == checkpoint and payload.get("scopeId") == scope_id


def maybe_crash(checkpoint: str, scope_id: str, requested: str | None = None) -> None:
    """Exit the process once for a matching certification transaction."""

    if not checkpoint or not scope_id or not _armed(checkpoint, scope_id, requested):
        return
    if crash_consumed(scope_id, checkpoint):
        return
    mark_crash_consumed(scope_id, checkpoint)
    arm = journal_path().parent / _ARM
    try:
        if arm.is_file():
            arm.unlink()
    except OSError:
        pass
    os._exit(86)
