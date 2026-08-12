"""Version 1.1 product-scope policy: native 3D deferred to Version 1.2.

Canonical machine-readable state is DEFERRED_VERSION_1_2. This is a deliberate
product decision — never present it as Failed / Missing / Blocked / Partial /
Install Required.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

# Canonical code (API + capability registry).
DEFERRED_VERSION_1_2 = "DEFERRED_VERSION_1_2"
DEFERRED_MESSAGE = (
    "Native 3D importing and animation are planned for Adept UI Version 1.2."
)
DEFERRED_LABEL = "Coming in Version 1.2"
DEFERRED_GUIDANCE = (
    "Version 1.1 uses 360 panoramic environments and Spatial Map production. "
    "Create a 360 Environment, open the Spatial Map, then set camera and lighting direction."
)

# HTTP status for policy denials (forbidden by product scope, not a missing route).
DEFERRED_HTTP_STATUS = 403


def deferred_detail(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": DEFERRED_VERSION_1_2,
        "message": DEFERRED_MESSAGE,
        "label": DEFERRED_LABEL,
        "guidance": DEFERRED_GUIDANCE,
    }
    payload.update(extra)
    return payload


def raise_deferred_3d(**extra: Any) -> None:
    """Raise a stable FastAPI HTTPException for deferred native-3D execution."""
    raise HTTPException(status_code=DEFERRED_HTTP_STATUS, detail=deferred_detail(**extra))
