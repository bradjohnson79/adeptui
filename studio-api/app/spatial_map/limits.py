from __future__ import annotations

from .errors import SpatialMapErrorCode, raise_http_error

CHARACTER_LIMIT = 4
PROP_LIMIT = 4
CAMERA_LIMIT = 4


def enforce_character_limit(count: int) -> None:
    if count >= CHARACTER_LIMIT:
        raise raise_http_error(
            SpatialMapErrorCode.CHARACTER_LIMIT_REACHED,
            limit=CHARACTER_LIMIT,
            count=count,
        )


def enforce_prop_limit(count: int) -> None:
    if count >= PROP_LIMIT:
        raise raise_http_error(
            SpatialMapErrorCode.PROP_LIMIT_REACHED,
            limit=PROP_LIMIT,
            count=count,
        )


def enforce_camera_limit(count: int) -> None:
    if count >= CAMERA_LIMIT:
        raise raise_http_error(
            SpatialMapErrorCode.CAMERA_LIMIT_REACHED,
            limit=CAMERA_LIMIT,
            count=count,
        )
