"""Duration is data. The orchestrator turns a request into legal provider pieces.

No provider receives a duration outside its declared capability.

All creator-facing duration is whole integer seconds. Frame-grid snapping
happens in the provider layer only (legalFrameCount). Never write frames/fps
back as canonical duration.
"""

from __future__ import annotations

from typing import Any

#: Maximum fractional drift (seconds) still considered an honest whole-second
#: float (15.0000001 → 15). Anything larger is rejected with a clear message.
_WHOLE_SECOND_EPSILON = 1e-6


class DurationUnsupported(Exception):
    def __init__(self, message: str, *, requested: float, supported: list[float], maximum: float | None):
        super().__init__(message)
        self.requested = requested
        self.supported = supported
        self.maximum = maximum

    def as_dict(self) -> dict[str, Any]:
        return {
            "error": "DURATION_UNSUPPORTED",
            "message": str(self),
            "requestedDurationSec": self.requested,
            "supportedDurations": self.supported,
            "maxDurationSec": self.maximum,
        }


def coerce_whole_seconds(value: float | int | None) -> int:
    """Normalize to an integer second. Reject real fractional drift.

    Float dust (15.0000001) is accepted and rounded to 15.
    Genuine fractional values (15.0833) are rejected with a clear diagnostic.
    """
    if value is None:
        raise DurationUnsupported(
            "Duration is required (whole seconds).",
            requested=0.0,
            supported=[],
            maximum=None,
        )
    try:
        sec = float(value)
    except (TypeError, ValueError):
        raise DurationUnsupported(
            f"{value!r} is not a valid duration.",
            requested=float(value) if isinstance(value, (int, float)) else 0.0,
            supported=[],
            maximum=None,
        )
    if not (sec > 0):
        raise DurationUnsupported(
            "Duration must be greater than zero.",
            requested=sec,
            supported=[],
            maximum=None,
        )
    nearest = round(sec)
    if abs(sec - nearest) > _WHOLE_SECOND_EPSILON:
        raise DurationUnsupported(
            f"{sec:g}s is not a whole second. Duration must be a whole number (e.g. 5, 10, 15). "
            f"The closest whole second is {nearest}s.",
            requested=sec,
            supported=[float(nearest)],
            maximum=None,
        )
    return nearest


def _assert_supported_piece(
    piece: float,
    supported: list[float],
    requested: float,
    maximum: float | None,
) -> None:
    """Every planned piece must itself be a declared provider capability.

    ``supportedDurations`` is the adapter's certified whole-second contract
    (e.g. LTX 2.5 = 4,6,...,20). A max-based split must not smuggle a piece
    outside that set — plan_duration may never hand a provider a duration it
    does not declare.
    """
    if not supported or any(abs(piece - item) < 0.01 for item in supported):
        return
    listed = ", ".join(f"{item:g}s" for item in supported)
    raise DurationUnsupported(
        f"This model can generate {listed}. {requested:g}s cannot be planned without a piece outside that set.",
        requested=requested,
        supported=supported,
        maximum=maximum,
    )


def plan_duration(requested: float, capabilities: Any) -> list[float]:
    """Return ordered legal integer piece lengths that sum to the request.

    H3/LTX use max-based splitting. API models with explicit duration slots
    (Veo, Kling) use coin composition.
    """
    whole = coerce_whole_seconds(requested)
    requested_f = float(whole)

    supported = [float(item) for item in (getattr(capabilities, "supportedDurations", None) or []) if float(item) > 0]
    maximum = getattr(capabilities, "maxDurationSec", None)
    maximum_f = float(maximum) if maximum not in (None, "") else None

    # --- exact match against supported list (API models with fixed slots) ---
    if supported and any(abs(requested_f - item) < 0.01 for item in supported):
        match = next(item for item in supported if abs(requested_f - item) < 0.01)
        return [float(match)]

    # --- coin composition for API fixed-slot models (Veo 4/6/8, Kling 5/10) ---
    if supported and maximum_f is None:
        target = int(requested_f)
        coins = [int(item) for item in supported if item == int(item)]
        if not coins:
            listed = ", ".join(f"{item:g}s" for item in supported)
            raise DurationUnsupported(
                f"This model can generate {listed}. {requested_f:g}s cannot be composed from those fixed lengths.",
                requested=requested_f,
                supported=supported,
                maximum=maximum_f,
            )
        pieces = _coin_compose(target, coins)
        if not pieces:
            listed = ", ".join(f"{item:g}s" for item in supported)
            raise DurationUnsupported(
                f"This model can generate {listed}. {requested_f:g}s is not an exact combination of those lengths.",
                requested=requested_f,
                supported=supported,
                maximum=maximum_f,
            )
        return [float(piece) for piece in pieces]

    # --- max-based splitting (H3 15s, LTX 20s) ---
    if maximum_f is None:
        raise DurationUnsupported(
            "This model has no declared duration limit, so the request cannot be planned.",
            requested=requested_f,
            supported=[],
            maximum=None,
        )

    max_whole = int(maximum_f)
    if requested_f <= maximum_f + 1e-6:
        piece = float(round(max(requested_f, 3.0)))
        _assert_supported_piece(piece, supported, requested_f, maximum_f)
        return [piece]

    pieces: list[float] = []
    remaining = whole
    while remaining > max_whole:
        _assert_supported_piece(float(max_whole), supported, requested_f, maximum_f)
        pieces.append(float(max_whole))
        remaining -= max_whole
    if remaining > 0:
        _assert_supported_piece(float(remaining), supported, requested_f, maximum_f)
        pieces.append(float(remaining))
    return pieces


def _coin_compose(target: int, coins: list[int]) -> list[int] | None:
    """Return a minimal-count combination of coins that sums exactly to target."""
    if target < 0:
        return None
    best: dict[int, list[int] | None] = {0: []}
    ordered = sorted(set(coins), reverse=True)
    for amount in range(1, target + 1):
        choice: list[int] | None = None
        for coin in ordered:
            if amount < coin:
                continue
            prev = best.get(amount - coin)
            if prev is None:
                continue
            candidate = prev + [coin]
            if choice is None or len(candidate) < len(choice):
                choice = candidate
        best[amount] = choice
    found = best.get(target)
    return list(found) if found is not None else None