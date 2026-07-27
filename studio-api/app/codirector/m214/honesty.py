"""Honest labels for M2.14 specialist scaffolds.

The M2.14 specialists are not yet bound to real providers. Labelling their output
`mocked` in production reads as "we generated something with a stand-in", which is a
claim the system cannot support. Outside E2E (and outside the explicitly-labelled
hitchhiker smoke surface) unbound specialists report `unavailable` instead.
"""

from __future__ import annotations

import os

MOCKED = "mocked"
UNAVAILABLE = "unavailable"
REAL = "real"
FIXTURE = "fixture"
SCAFFOLDED = "scaffolded"

HONESTY_VALUES = (MOCKED, REAL, FIXTURE, UNAVAILABLE, SCAFFOLDED)

_TRUE = {"1", "true", "TRUE", "yes", "YES", "on"}


def e2e_enabled() -> bool:
    return os.environ.get("STUDIO_E2E", "").strip() in _TRUE


def default_honesty(*, demo: bool = False) -> str:
    """Label for output produced by an unbound specialist.

    `demo=True` marks the hitchhiker smoke surface, which is explicitly a labelled
    walkthrough rather than a production claim.
    """
    return MOCKED if (demo or e2e_enabled()) else UNAVAILABLE


def unbound_note(specialist: str) -> str:
    if e2e_enabled():
        return f"{specialist} is running deterministic E2E output, not a real provider."
    return (
        f"{specialist} is not bound to a real provider yet; this is a structural scaffold "
        "and must not be treated as generated content."
    )
