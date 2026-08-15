from __future__ import annotations

from app.codirector.execution.dispatcher import (
    _creator_readable_handler_error,
    creator_readable_handler_error,
)
from app.spatial_map.capture_intelligence import SpatialCaptureGeometryError


def test_handler_error_never_raw_typeerror() -> None:
    exc = TypeError("unsupported operand type(s) for -: 'NoneType' and 'float'")
    msg = creator_readable_handler_error(exc)
    assert msg == _creator_readable_handler_error(exc)
    assert "HANDLER_ERROR" not in msg
    assert "TypeError" in msg
    assert "None" in msg
    assert "unsupported operand" in msg


def test_handler_error_domain_geometry_passthrough() -> None:
    exc = SpatialCaptureGeometryError(
        "Key Prop is required on the Spatial Map but has no world position. "
        "Place it on the grid or attach it to a character before generating."
    )
    msg = creator_readable_handler_error(exc)
    assert msg == str(exc)
    assert "HANDLER_ERROR" not in msg
    assert not msg.startswith("TypeError")
